from osmclient import client
from osmclient.common.exceptions import ClientException
import yaml
from prettytable import PrettyTable
import contextlib
import os
import shutil
import tempfile


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

    def connect(self, addr="127.0.0.1", port=9999):
        self.sess = client.Client(host=addr, sol005=True, **self.kwargs)

    def get_vnfd(self):
        resp = self.sess.vnfd.list()
        return resp

    def get_vim(self):
        resp = self.sess.vim.list()
        return resp

    def create_vnfd():
       pass
