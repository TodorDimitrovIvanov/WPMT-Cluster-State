from pydantic import BaseModel
import datetime
from pymongo import MongoClient
from pprint import pprint
import requests
import json
from fastapi import FastAPI, HTTPException
import uvicorn

app = FastAPI()

__master_url__ = "https://master.wpmt.org"

__cluster_name__ = "cluster-eu01.wpmt.org"
__cluster_url__ = "https://cluster-eu01.wpmt.org"
__cluster_logger_url__ = "http://cluster-eu01.wpmt.tech/log/save"
__cluster_locale__ = "EU"
__cluster_user_count__ = None

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
    def init():
        db = DB.connect()
        states_collection = db['states']

        temp_time = datetime.datetime.utcnow()
        now = temp_time.strftime("%b-%d-%Y-%H:%M")

        init_document = {"init_time": str(now)}

        result = states_collection.insert_one(init_document)

        db_list = db.list_database_names()
        if __mongo_host__ in db_list:
            db_collections = db.list_collection_names()
            if "states" in db_collections:
                return {
                    "Response": "Success",
                    "Message": "MongoDB Initialized"
                }
            else:
                return {
                    "Response": "Error",
                    "Message": "MongoDB Init Failed"
                }
        else:
            return {
                "Response": "Error",
                "Message": "MongoDB Init Failed"
            }


    @staticmethod
    def connect():
        client = MongoClient(__mongo_host__)
        db = client[__mongo_db__]
        return db


class PostStateGet(BaseModel):
    client_id: str


class PostStateCompare(BaseModel):
    client_id: str
    client_last_update: str


class PostStateSet(BaseModel):
    client_id: str
    state_obj: dict


@app.post("/state/get", status_code=200)
def cluster_state_get(post_data: PostStateGet):
    post_data_dict = post_data.dict()




@staticmethod
def cluster_state_compare(client_id: str, client_last_update: str):
    pass


@staticmethod
def cluster_state_set(client_id: str, state_obj: dict):


    pass





if __name__ == "__main__":
    # Here we must use 127.0.0.1 as K8s doesn't seem to recognize localhost ....
    uvicorn.run(app, host='127.0.0.1', port=6902)


