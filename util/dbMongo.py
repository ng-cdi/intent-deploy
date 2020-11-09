# -*- coding: utf-8 -*-

# Copyright 2018 Telefonica S.A.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import logging
from pymongo import MongoClient, errors
from util.dbBase import DbException, DbBase
from http import HTTPStatus
from time import time, sleep
from copy import deepcopy
from base64 import b64decode
from uuid import uuid4

__author__ = "Alfonso Tierno <alfonso.tiernosepulveda@telefonica.com>"

# TODO consider use this decorator for database access retries
# @retry_mongocall
# def retry_mongocall(call):
#     def _retry_mongocall(*args, **kwargs):
#         retry = 1
#         while True:
#             try:
#                 return call(*args, **kwargs)
#             except pymongo.AutoReconnect as e:
#                 if retry == 4:
#                     raise DbException(e)
#                 sleep(retry)
#     return _retry_mongocall


def deep_update(to_update, update_with):
    """
    Similar to deepcopy but recursively with nested dictionaries. 'to_update' dict is updated with a content copy of
    'update_with' dict recursively
    :param to_update: must be a dictionary to be modified
    :param update_with: must be a dictionary. It is not changed
    :return: to_update
    """
    for key in update_with:
        if key in to_update:
            if isinstance(to_update[key], dict) and isinstance(update_with[key], dict):
                deep_update(to_update[key], update_with[key])
                continue
        to_update[key] = deepcopy(update_with[key])
    return to_update


class DbMongo(DbBase):
    conn_initial_timout = 120
    conn_timout = 10

    def __init__(self, logger_name='db', lock=True):
        super().__init__(logger_name, lock)
        self.client = None
        self.db = None
        self.database_key = None
        self.secret_obtained = False
        # ^ This is used to know if database serial has been got. Database is inited by NBI, who generates the serial
        # In case it is not ready when connected, it should be got later on before any decrypt operation

    def get_secret_key(self):
        if self.secret_obtained:
            return

        self.secret_key = None
        if self.database_key:
            self.set_secret_key(self.database_key)
        version_data = self.get_one("admin", {"_id": "version"}, fail_on_empty=False, fail_on_more=True)
        if version_data and version_data.get("serial"):
            self.set_secret_key(b64decode(version_data["serial"]))
        self.secret_obtained = True

    def db_connect(self, config, target_version=None):
        """
        Connect to database
        :param config: Configuration of database
        :param target_version: if provided it checks if database contains required version, raising exception otherwise.
        :return: None or raises DbException on error
        """
        try:
            if "logger_name" in config:
                self.logger = logging.getLogger(config["logger_name"])
            master_key = config.get("commonkey") or config.get("masterpassword")
            if master_key:
                self.database_key = master_key
                self.set_secret_key(master_key)
            if config.get("uri"):
                self.client = MongoClient(config["uri"])
            else:
                self.client = MongoClient(config["host"], config["port"])
            # TODO add as parameters also username=config.get("user"), password=config.get("password"))
            # when all modules are ready
            self.db = self.client[config["name"]]
            if "loglevel" in config:
                self.logger.setLevel(getattr(logging, config['loglevel']))
            return
            # get data to try a connection
        #     now = time()
        #     while True:
        #         try:
        #             version_data = self.get_one("admin", {"_id": "version"}, fail_on_empty=False, fail_on_more=True)
        #             # check database status is ok
        #             if version_data and version_data.get("status") != 'ENABLED':
        #                 raise DbException("Wrong database status '{}'".format(version_data.get("status")),
        #                                   http_code=HTTPStatus.INTERNAL_SERVER_ERROR)
        #             # check version
        #             db_version = None if not version_data else version_data.get("version")
        #             if target_version and target_version != db_version:
        #                 raise DbException("Invalid database version {}. Expected {}".format(db_version, target_version))
        #             # get serial
        #             if version_data and version_data.get("serial"):
        #                 self.secret_obtained = True
        #                 self.set_secret_key(b64decode(version_data["serial"]))
        #             self.logger.info("Connected to database {} version {}".format(config["name"], db_version))
        #             return
        #         except errors.ConnectionFailure as e:
        #             if time() - now >= self.conn_initial_timout:
        #                 raise
        #             self.logger.info("Waiting to database up {}".format(e))
        #             sleep(2)
        except errors.PyMongoError as e:
            raise DbException(e)

    @staticmethod
    def _format_filter(q_filter):
        """
        Translate query string q_filter into mongo database filter
        :param q_filter: Query string content. Follows SOL005 section 4.3.2 guidelines, with the follow extensions and
        differences:
            It accept ".nq" (not equal) in addition to ".neq".
            For arrays you can specify index (concrete index must match), nothing (any index may match) or 'ANYINDEX'
            (two or more matches applies for the same array element). Examples:
                with database register: {A: [{B: 1, C: 2}, {B: 6, C: 9}]}
                query 'A.B=6' matches because array A contains one element with B equal to 6
                query 'A.0.B=6' does no match because index 0 of array A contains B with value 1, but not 6
                query 'A.B=6&A.C=2' matches because one element of array matches B=6 and other matchesC=2
                query 'A.ANYINDEX.B=6&A.ANYINDEX.C=2' does not match because it is needed the same element of the
                    array matching both

        Examples of translations from SOL005 to  >> mongo  # comment
            A=B; A.eq=B         >> A: B             # must contain key A and equal to B or be a list that contains B
            A.cont=B            >> A: B
            A=B&A=C; A=B,C      >> A: {$in: [B, C]} # must contain key A and equal to B or C or be a list that contains
                # B or C
            A.cont=B&A.cont=C; A.cont=B,C  >> A: {$in: [B, C]}
            A.ncont=B           >> A: {$nin: B}     # must not contain key A or if present not equal to B or if a list,
                # it must not not contain B
            A.ncont=B,C; A.ncont=B&A.ncont=C    >> A: {$nin: [B,C]}     # must not contain key A or if present not equal
                # neither B nor C; or if a list, it must not contain neither B nor C
            A.ne=B&A.ne=C; A.ne=B,C             >> A: {$nin: [B, C]}
            A.gt=B              >> A: {$gt: B}      # must contain key A and greater than B
            A.ne=B; A.neq=B         >> A: {$ne: B}          # must not contain key A or if present not equal to B, or if
                # an array not contain B
            A.ANYINDEX.B=C          >> A: {$elemMatch: {B=C}
        :return: database mongo filter
        """
        try:
            db_filter = {}
            if not q_filter:
                return db_filter
            for query_k, query_v in q_filter.items():
                dot_index = query_k.rfind(".")
                if dot_index > 1 and query_k[dot_index+1:] in ("eq", "ne", "gt", "gte", "lt", "lte", "cont",
                                                               "ncont", "neq"):
                    operator = "$" + query_k[dot_index + 1:]
                    if operator == "$neq":
                        operator = "$ne"
                    k = query_k[:dot_index]
                else:
                    operator = "$eq"
                    k = query_k

                v = query_v
                if isinstance(v, list):
                    if operator in ("$eq", "$cont"):
                        operator = "$in"
                        v = query_v
                    elif operator in ("$ne", "$ncont"):
                        operator = "$nin"
                        v = query_v
                    else:
                        v = query_v.join(",")

                if operator in ("$eq", "$cont"):
                    # v cannot be a comma separated list, because operator would have been changed to $in
                    db_v = v
                elif operator == "$ncount":
                    # v cannot be a comma separated list, because operator would have been changed to $nin
                    db_v = {"$ne": v}
                else:
                    db_v = {operator: v}

                # process the ANYINDEX word at k.
                kleft, _, kright = k.rpartition(".ANYINDEX.")
                while kleft:
                    k = kleft
                    db_v = {"$elemMatch": {kright: db_v}}
                    kleft, _, kright = k.rpartition(".ANYINDEX.")

                # insert in db_filter
                # maybe db_filter[k] exist. e.g. in the query string for values between 5 and 8: "a.gt=5&a.lt=8"
                deep_update(db_filter, {k: db_v})

            return db_filter
        except Exception as e:
            raise DbException("Invalid query string filter at {}:{}. Error: {}".format(query_k, v, e),
                              http_code=HTTPStatus.BAD_REQUEST)

    def get_list(self, table, q_filter=None):
        """
        Obtain a list of entries matching q_filter
        :param table: collection or table
        :param q_filter: Filter
        :return: a list (can be empty) with the found entries. Raises DbException on error
        """
        try:
            result = []
            with self.lock:
                collection = self.db[table]
                db_filter = self._format_filter(q_filter)
                rows = collection.find(db_filter)
            for row in rows:
                result.append(row)
            return result
        except DbException:
            raise
        except Exception as e:  # TODO refine
            raise DbException(e)

    def count(self, table, q_filter=None):
        """
        Count the number of entries matching q_filter
        :param table: collection or table
        :param q_filter: Filter
        :return: number of entries found (can be zero)
        :raise: DbException on error
        """
        try:
            with self.lock:
                collection = self.db[table]
                db_filter = self._format_filter(q_filter)
                count = collection.count(db_filter)
            return count
        except DbException:
            raise
        except Exception as e:  # TODO refine
            raise DbException(e)

    def get_one(self, table, q_filter=None, fail_on_empty=True, fail_on_more=True):
        """
        Obtain one entry matching q_filter
        :param table: collection or table
        :param q_filter: Filter
        :param fail_on_empty: If nothing matches filter it returns None unless this flag is set tu True, in which case
        it raises a DbException
        :param fail_on_more: If more than one matches filter it returns one of then unless this flag is set tu True, so
        that it raises a DbException
        :return: The requested element, or None
        """
        try:
            db_filter = self._format_filter(q_filter)
            with self.lock:
                collection = self.db[table]
                if not (fail_on_empty and fail_on_more):
                    return collection.find_one(db_filter)
                rows = collection.find(db_filter)
            if rows.count() == 0:
                if fail_on_empty:
                    raise DbException("Not found any {} with filter='{}'".format(table[:-1], q_filter),
                                      HTTPStatus.NOT_FOUND)
                return None
            elif rows.count() > 1:
                if fail_on_more:
                    raise DbException("Found more than one {} with filter='{}'".format(table[:-1], q_filter),
                                      HTTPStatus.CONFLICT)
            return rows[0]
        except Exception as e:  # TODO refine
            raise DbException(e)

    def del_list(self, table, q_filter=None):
        """
        Deletes all entries that match q_filter
        :param table: collection or table
        :param q_filter: Filter
        :return: Dict with the number of entries deleted
        """
        try:
            with self.lock:
                collection = self.db[table]
                rows = collection.delete_many(self._format_filter(q_filter))
            return {"deleted": rows.deleted_count}
        except DbException:
            raise
        except Exception as e:  # TODO refine
            raise DbException(e)

    def del_one(self, table, q_filter=None, fail_on_empty=True):
        """
        Deletes one entry that matches q_filter
        :param table: collection or table
        :param q_filter: Filter
        :param fail_on_empty: If nothing matches filter it returns '0' deleted unless this flag is set tu True, in
        which case it raises a DbException
        :return: Dict with the number of entries deleted
        """
        try:
            with self.lock:
                collection = self.db[table]
                rows = collection.delete_one(self._format_filter(q_filter))
            if rows.deleted_count == 0:
                if fail_on_empty:
                    raise DbException("Not found any {} with filter='{}'".format(table[:-1], q_filter),
                                      HTTPStatus.NOT_FOUND)
                return None
            return {"deleted": rows.deleted_count}
        except Exception as e:  # TODO refine
            raise DbException(e)

    def create(self, table, indata):
        """
        Add a new entry at database
        :param table: collection or table
        :param indata: content to be added
        :return: database id of the inserted element. Raises a DbException on error
        """
        try:
            with self.lock:
                collection = self.db[table]
                data = collection.insert_one(indata)
            return data.inserted_id
        except Exception as e:  # TODO refine
            raise DbException(e)

    def create_list(self, table, indata_list):
        """
        Add several entries at once
        :param table: collection or table
        :param indata_list: content list to be added.
        :return: the list of inserted '_id's. Exception on error
        """
        try:
            for item in indata_list:
                if item.get("_id") is None:
                    item["_id"] = str(uuid4())
            with self.lock:
                collection = self.db[table]
                data = collection.insert_many(indata_list)
            return data.inserted_ids
        except Exception as e:  # TODO refine
            raise DbException(e)

    def set_one(self, table, q_filter, update_dict, fail_on_empty=True, unset=None, pull=None, push=None,
                push_list=None, pull_list=None):
        """
        Modifies an entry at database
        :param table: collection or table
        :param q_filter: Filter
        :param update_dict: Plain dictionary with the content to be updated. It is a dot separated keys and a value
        :param fail_on_empty: If nothing matches filter it returns None unless this flag is set tu True, in which case
        it raises a DbException
        :param unset: Plain dictionary with the content to be removed if exist. It is a dot separated keys, value is
                      ignored. If not exist, it is ignored
        :param pull: Plain dictionary with the content to be removed from an array. It is a dot separated keys and value
                     if exist in the array is removed. If not exist, it is ignored
        :param pull_list: Same as pull but values are arrays where each item is removed from the array
        :param push: Plain dictionary with the content to be appended to an array. It is a dot separated keys and value
                     is appended to the end of the array
        :param push_list: Same as push but values are arrays where each item is and appended instead of appending the
                          whole array
        :return: Dict with the number of entries modified. None if no matching is found.
        """
        try:
            db_oper = {}
            if update_dict:
                db_oper["$set"] = update_dict
            if unset:
                db_oper["$unset"] = unset
            if pull or pull_list:
                db_oper["$pull"] = pull or {}
                if pull_list:
                    db_oper["$pull"].update({k: {"$in": v} for k, v in pull_list.items()})
            if push or push_list:
                db_oper["$push"] = push or {}
                if push_list:
                    db_oper["$push"].update({k: {"$each": v} for k, v in push_list.items()})

            with self.lock:
                collection = self.db[table]
                rows = collection.update_one(self._format_filter(q_filter), db_oper)
            if rows.matched_count == 0:
                if fail_on_empty:
                    raise DbException("Not found any {} with filter='{}'".format(table[:-1], q_filter),
                                      HTTPStatus.NOT_FOUND)
                return None
            return {"modified": rows.modified_count}
        except Exception as e:  # TODO refine
            raise DbException(e)

    def set_list(self, table, q_filter, update_dict, unset=None, pull=None, push=None, push_list=None, pull_list=None):
        """
        Modifies al matching entries at database
        :param table: collection or table
        :param q_filter: Filter
        :param update_dict: Plain dictionary with the content to be updated. It is a dot separated keys and a value
        :param unset: Plain dictionary with the content to be removed if exist. It is a dot separated keys, value is
                      ignored. If not exist, it is ignored
        :param pull: Plain dictionary with the content to be removed from an array. It is a dot separated keys and value
                     if exist in the array is removed. If not exist, it is ignored
        :param push: Plain dictionary with the content to be appended to an array. It is a dot separated keys, the
                     single value is appended to the end of the array
        :param pull_list: Same as pull but values are arrays where each item is removed from the array
        :param push_list: Same as push but values are arrays where each item is and appended instead of appending the
                          whole array
        :return: Dict with the number of entries modified
        """
        try:
            db_oper = {}
            if update_dict:
                db_oper["$set"] = update_dict
            if unset:
                db_oper["$unset"] = unset
            if pull or pull_list:
                db_oper["$pull"] = pull or {}
                if pull_list:
                    db_oper["$pull"].update({k: {"$in": v} for k, v in pull_list.items()})
            if push or push_list:
                db_oper["$push"] = push or {}
                if push_list:
                    db_oper["$push"].update({k: {"$each": v} for k, v in push_list.items()})
            with self.lock:
                collection = self.db[table]
                rows = collection.update_many(self._format_filter(q_filter), db_oper)
            return {"modified": rows.modified_count}
        except Exception as e:  # TODO refine
            raise DbException(e)

    def replace(self, table, _id, indata, fail_on_empty=True):
        """
        Replace the content of an entry
        :param table: collection or table
        :param _id: internal database id
        :param indata: content to replace
        :param fail_on_empty: If nothing matches filter it returns None unless this flag is set tu True, in which case
        it raises a DbException
        :return: Dict with the number of entries replaced
        """
        try:
            db_filter = {"_id": _id}
            with self.lock:
                collection = self.db[table]
                rows = collection.replace_one(db_filter, indata)
            if rows.matched_count == 0:
                if fail_on_empty:
                    raise DbException("Not found any {} with _id='{}'".format(table[:-1], _id), HTTPStatus.NOT_FOUND)
                return None
            return {"replaced": rows.modified_count}
        except Exception as e:  # TODO refine
            raise DbException(e)       
