from typing import Optional

import pymongo.errors
from pydantic import BaseModel
import datetime
from pymongo import MongoClient
import requests
import json
from fastapi import FastAPI, HTTPException
import uvicorn

app = FastAPI()

__master_url__ = "http://master.wpmt.org"

__cluster_name__ = "cluster-eu01.wpmt.org"
__cluster_url__ = "http://cluster-eu01.wpmt.org"
__cluster_logger_url__ = "http://cluster-eu01.wpmt.org/log/save"
__cluster_locale__ = "EU"

__mysql_host__ = "localhost"
__mysql_db__ = "cluster_eu01"
__mysql_user__ = "cluser_eu01_user"
# Temporarily disabled:
# The API should receive the password via system's environment variable
# This variable is set by Kubernetes via the "secretGenerator.yaml" file
# Source: https://stackoverflow.com/questions/60343474/how-to-get-secret-environment-variables-implemented-by-kubernetes-into-python
#   __mysql_pass__ = environ['MYSQL_USER_PASSWORD']
__mysql_pass__ = "kP6hE3zE7aJ7nQ6i"


__mongo_host__ = "mongodb://localhost:27017/"
__mongo_db__ = "cluster_eu01_mongo"
__mongo_user__ = "cluster_eu01_user"
# Disabled due to the same reason from above
# __mongo_pass__ = environ['MONGO_USER_PASSWORD']
__mongo_pass__ = "kP6hE3zE7aJ7nQ6i"

__app_headers__ = {
    'Host': 'cluster-eu01.wpmt.org',
    'User-Agent': 'WPMT-Auth/1.0',
    'Referer': 'http://cluster-eu01.wpmt.org/user',
    'Content-Type': 'application/json'
}


def send_to_logger(err_type, message, client_id="None", client_email="None"):
    # TODO: Find a way to get the user's IP address and add it to the message
    print("Message: ", message, "Type: ", err_type)
    global __app_headers__
    body = {
        "client_id": client_id,
        "email": client_email,
        "type": err_type,
        "message": message
    }
    send_request = requests.post(__cluster_logger_url__, data=json.dumps(body), headers=__app_headers__)


# -------------------
# START of DB section
# -------------------
class DB:

    @staticmethod
    def init_db():
        # Here we start the MongoDB connection using the MongoClient via the "connect()" function
        # This returns the __mongo_db__ Mongo database object
        db = DB.connect()
        # A collection in MongoDB is the same as a table in MySQL and her we declare a "user_states" collection
        states_collection = db['user_states']
        # Here we prepare a timestamp for when the collection was created.
        # Unless some document (row) is saved within a collection, Mongo won't save it to the disk and remains within the memory
        temp_time = datetime.datetime.utcnow()
        now = temp_time.strftime("%b-%d-%Y-%H:%M")
        init_document = {"init_time": str(now)}
        # Here we insert the init_document we setup above
        result = states_collection.insert_one(init_document)

        # Once this is done we need to verify that the setup has been completed
        db_names_list = db.list_database_names()
        if __mongo_db__ in db_names_list:
            db_collection_names = db.list_collection_names()
            if "states" in db_collection_names:
                return {
                    "Response": "Success",
                    "Message": "MongoDB Initialized"
                }
            # If the "states" collection doesn't exist:
            else:
                message = "[Cluster][Mongo][Error][04]: Can't select the 'states' collection!"
                send_to_logger("error", message, client_id="None", client_email="None")
                return {
                    "Response": "Error",
                    "Message": message
                }
        # If the database doesn't exist or can't be selected
        else:
            message = "[Cluster][Mongo][Error][03]: Can't select DB!"
            send_to_logger("error", message, client_id="None", client_email="None")
            return {
                "Response": "Error",
                "Message": message
            }


    @staticmethod
    def connect():
        try:
            client = MongoClient(__mongo_host__)
            db = client[__mongo_db__]
            if db is None:
                return {
                    "Response": "Error",
                    "Message": "[Cluster][Mongo][Error][02]: Can't open the DB!"
                }
            else:
                return db
        except pymongo.errors.PyMongoError as err:
            message = "[Cluster][Mongo][Error][01]: Can't connect to the Mongo service. Full Error: " + str(err)
            send_to_logger("error", message, client_id="None", client_email="None")
            return {
                "Response": "Error",
                "Message": message
            }
# -------------------
# START of DB section
# -------------------


# -------------------------
# START of Models section
# -------------------------
class PostStateGet(BaseModel):
    client_id: str


class PostStateCompare(BaseModel):
    state_obj: dict


class PostStateSet(BaseModel):
    state_obj: dict
# -------------------------
# END of Models section
# -------------------------


# -------------------------
# START of Cluster section
# -------------------------
class Cluster:

    @staticmethod
    def user_state_get(client_id: str):
        db_conn = DB.connect()
        db_coll = db_conn['user_states']
        db_data = {"client_id": client_id}
        # Here we fetch the document but exclude the Mongo "_id" key
        # Since it's causing an issue with the Starlette/FastAPI service
        # Source: https://stackoverflow.com/a/64792159
        db_result = db_coll.find_one(db_data, {'_id': 0})
        if db_result is None:
            return {
                "Response": "Error",
                "Message": "Not Found"
            }
        else:
            return db_result


    @staticmethod
    def user_state_compare(client_state_obj):
        # Source: https://stackoverflow.com/a/20365917
        db_conn = DB.connect()
        db_coll = db_conn['user_states']
        db_data = {"client_id": client_state_obj['client_id']}
        db_result = db_coll.find_one(db_data)
        # Here we'll compare the last update on the Client and the Cluster
        # Source: https://stackoverflow.com/a/20365903
        temp = db_result['last_update']
        cluster_state_last_update = datetime.datetime.strptime(temp, "%b-%d-%Y-%H:%M")
        client_state_last_update = datetime.datetime.strptime(client_state_obj['last_update'], "%b-%d-%Y-%H:%M")
        if cluster_state_last_update > client_state_last_update:
            state_obj = Cluster.user_state_get(client_state_obj['client_id'])
            return {
                "Response": "client-update",
                "State": state_obj
            }
        if cluster_state_last_update == client_state_last_update:
            return {
                "Response": "synced",
                "State": client_state_obj
            }
        else:
            Cluster.user_state_set(client_state_obj)
            result = Cluster.user_state_get(client_state_obj['client_id'])
            return {
                "Response": "cluster-update",
                "State": result
            }


    @staticmethod
    def user_state_set(state_obj: dict):
        db_conn = DB.connect()
        db_coll = db_conn['user_states']
        db_data = state_obj
        # Here the "upsert" parameter tells mongo to create the document if no matches were found
        # This is useful for using the function as an update and an insert command
        # Source: https://www.geeksforgeeks.org/python-mongodb-update_one/
        # The $set operator specifies which data is to be updated
        #db_result = db_coll.update_one({"client_id": state_obj['client_id']}, {"$set": {"state": db_data}}, upsert=True)
        db_result = db_coll.insert({"_id": state_obj['client_id'], "state": db_data})
        if db_result is None:
            return {
                "Response": "Success",
                "Message": "Successfully set the state for user [" + state_obj['client_id'] + "] "
            }
        else:
            return db_result

# -------------------------
# END of Cluster section
# -------------------------


# -------------------------
# START of FastAPI section
# -------------------------
@app.post("/state/get", status_code=200)
def cluster_state_get(post_data: PostStateGet):
    post_data_dict = post_data.dict()
    result = Cluster.user_state_get(post_data_dict['client_id'])
    # Here the function returns a dict with nested dicts within it. The keys of the dict are:
    # client_id
    # last_update
    # website_states - this should contain nested dicts
    # wordpress_states - this should contain nested dicts
    # backup_states - this should contain nested dicts
    # notification_states - this should contain nested dicts
    return result


# Not sure if this endpoint should even exist.
# This is because the WPMT Client should automatically sync every n minutes with the '/state/compare' endpoint
@app.post("/state/set", status_code=200)
def cluster_state_set(post_data: PostStateSet):
    post_data_dict = post_data.dict()
    temp = Cluster.user_state_set(post_data_dict['state_obj'])
    return {
        "Response": "Success",
        "Message": "State successfully updated",
        "State": post_data_dict
    }


@app.get("/state/db_init", status_code=200)
def mongo_db_init():
    # TODO: Add authorization for support user
    DB.init_db()


@app.post("/state/compare", status_code=200)
def cluster_state_compare(post_data: PostStateCompare):
    post_data_dict = post_data.dict()
    result = Cluster.user_state_compare(post_data_dict['state_obj'])
    return result
# -------------------------
# END of FastAPI section
# -------------------------


if __name__ == "__main__":
    # Here we must use 127.0.0.1 as K8s doesn't seem to recognize localhost ....
    uvicorn.run(app, host='127.0.0.1', port=6903)


