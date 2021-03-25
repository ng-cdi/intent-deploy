import logging
from typing import Any, List
from osmclient import client
from osmclient.common.exceptions import ClientException
import yaml
from prettytable import PrettyTable
import contextlib
import os
import shutil
import tempfile
from osmclient.sol005.vnfd import Vnfd
from osmclient.sol005.vim import Vim


class OSMDeploy(object):
    """
    This is a test class to exercise the API for an OSM deployer.

    TODO:
    * What are doing with the network?
    * How do we know the available resources?
    """

    def __init__(self, user=None, password = None, project = None):
        """
        docstring
        """
        self.kwargs = {}
        if user is not None:
            self.kwargs['user']=user
        if password is not None:
            self.kwargs['password']=password
        if project is not None:
           self.kwargs['project']=project

    def connect(self, addr : str ="127.0.0.1", port : int =9999):
        self.sess : client.Client = client.Client(host=addr, sol005=True, **self.kwargs)

    def get_vnfd(self) -> List[Vnfd]:
        resp = self.sess.vnfd.list()
        logging.info(resp)
        return resp

    def get_vim(self) -> List[Vim]:
        resp = self.sess.vim.list()
        return resp

    def create_nsd(self, filename : str) -> Any:
        resp = self.sess.nsd.create(filename)
        return resp

    def create_ns(self, nsd_name : str, ns_name : str, vim : str) : 
        resp = self.sess.ns.create(nsd_name, ns_name, vim)
        return resp