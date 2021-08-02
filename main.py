from typing import Optional

import pymongo.errors
from pydantic import BaseModel
import datetime
from pymongo import MongoClient
from pprint import pprint
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


__mongo_host__ = "mongodb://localhost:3307/"
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



    @staticmethod
    def execute_command(database_obj, command: str, data: Optional[list] = []):
        db_client = DB.connect()



class PostStateGet(BaseModel):
    client_id: str


class PostStateCompare(BaseModel):
    client_id: str
    client_last_update: str


class PostStateSet(BaseModel):
    client_id: str
    state_obj: dict


class Cluster:

    @staticmethod
    def user_state_get(client_id: str):
        db_conn = DB.connect()
        db_coll = db_conn['user_states']
        db_command = {"client_id": client_id}
        db_result = db_coll.find(db_command)
        for item in db_result:
            pprint(item)

    @staticmethod
    def user_state_compare(client_id: str, client_last_update: str):
        pass

    @staticmethod
    def user_state_set(client_id: str, state_obj: dict):
        pass


@app.post("/state/get", status_code=200)
def cluster_state_get(post_data: PostStateGet):
    post_data_dict = post_data.dict()
    Cluster.user_state_get(post_data_dict['client_id'])

    # To be continued


@app.post("/state/set", status_code=200)
def cluster_state_set(post_data: PostStateSet):
    print("Kurec1")


@app.post("/state/compare", status_code=200)
def cluster_state_set(post_data: PostStateCompare):
    print("Kurec2")


if __name__ == "__main__":
    # Here we must use 127.0.0.1 as K8s doesn't seem to recognize localhost ....
    uvicorn.run(app, host='127.0.0.1', port=6903)


