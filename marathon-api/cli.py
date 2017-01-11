#!/usr/bin/env python

from __future__ import absolute_import
import krux.logging
import sys
import socket
import json
from pprint import pprint
from marathon import MarathonClient
from marathon.models import MarathonApp
from krux.cli import Application, get_group, get_parser


class MarathonClientApp(Application):

    def __init__(self):
        super(MarathonClientApp, self).__init__(name='marathonclientapp', syslog_facility='local0')
        self.marathon_host = self.args.host
        self.marathon_port = self.args.port
        self.marathon_list_apps = self.args.list_apps
        self.marathon_config_file = self.args.config_file

    def add_cli_arguments(self, parser):
        """
        Adds command line arguments, these options can be seen using -h when calling the app.
        """
        super(MarathonClientApp, self).add_cli_arguments(parser)
        group = get_group(parser, self.name)

        group.add_argument(
            '--host',
            default='localhost',
            help='Marathon server host name or IP address. ',
        )
        group.add_argument(
            '--port',
            default='8080',
            help='Marathon server port. ',
        )
        group.add_argument(
            '--list_apps',
            action='store_true',
            default=False,
            help='Use flag to list all marathon apps. ',
        )
        group.add_argument(
            '--config_file',
            help='Marathon config file to configure app. ',
        )
        group.add_argument(
            '--get_app',
            default=False,
            help='app flag can be used to pass an app name to get '
            'more detailed info on a running app ',
        )
        group.add_argument(
            '--delete',
            action='store_true',
            default=False,
            help='Set flag to delete an app '
        )

    def connect(self, address, port):
        """
        Tests connecting to the Marathon Server given. Takes in a host and port.
        If the values weren't passed on the command line, defaults will be used.
        If the connection fails, the program will stop and exit with a value of 1.
        """
        self.logger.info("Testing connection to marathon server")
        self.logger.info('host = ' + address)
        self.logger.info('port = ' + str(port))

        try:
            s = socket.socket()
            s.connect((address, port))
        except Exception as e:
            self.logger.error("something's wrong with %s:%d. Exception is %s" % (address, port, e))
            sys.exit(1)
        finally:
            s.close()

    def read_config_file(self, config_file):
        """
        Open the json file passed on the command line. The program will stop and
        exit with a value of 1 if it cannot open or parse the json file.
        """
        self.logger.info("Reading config file and formatting data.")
        self.logger.info(config_file)
        ### open and load json config file
        try:
            with open(config_file) as data_file:
                data = json.load(data_file)
        except Exception as e:
            self.logger.error("Error in json file:  %s. Exception is %s" % (config_file, e))
            sys.exit(1)
        return data

    def assign_config_data(self, config_file_data, marathon_app_result):
        """
        Assign variables from the config file to the marathon app values.
        We cannot use a dymnamic variable so we are assigning these one at a time.
        """
        ### assigning values from json to our marathon app
        self.logger.info("Assigning json variables to app data")
        marathon_app_result.cpus                     = config_file_data["cpus"]
        marathon_app_result.mem                      = config_file_data["mem"]
        marathon_app_result.instances                = config_file_data["instances"]
        marathon_app_result.disk                     = config_file_data["disk"]
        marathon_app_result.cmd                      = config_file_data["cmd"]
        marathon_app_result.backoff_factor           = config_file_data["backoff_factor"]
        marathon_app_result.constraints              = config_file_data["constraints"]
        marathon_app_result.container                = config_file_data["container"]
        marathon_app_result.dependencies             = config_file_data["dependencies"]
        marathon_app_result.env                      = config_file_data["env"]
        marathon_app_result.executor                 = config_file_data["executor"]
        marathon_app_result.health_checks            = config_file_data["health_checks"]
        marathon_app_result.labels                   = config_file_data["labels"]
        marathon_app_result.max_launch_delay_seconds = config_file_data["max_launch_delay_seconds"]
        #marathon_app_result.ports = config_file_data["ports"]      # You cannot specify both ports and port definitions
        marathon_app_result.require_ports            = config_file_data["require_ports"]
        marathon_app_result.store_urls               = config_file_data["store_urls"]
        marathon_app_result.upgrade_strategy         = config_file_data["upgrade_strategy"]
        marathon_app_result.uris                     = config_file_data["uris"]
        marathon_app_result.user                     = config_file_data["user"]                 #updates confirmed

    def list_marathon_apps(self, marathon_server):
        """
        This method connects to the marathon server and requests all the
        Marathon Apps.
        """
        self.logger.info("Listing apps running on marathon")
        current_marathon_apps = marathon_server.list_apps()
        self.logger.info(current_marathon_apps)

    def get_marathon_app(self, marathon_server, config_file_data):
        """
        Connects to the Marathon Server using the supplied App ID.
        If we passed the config file and the App isn't found on the server, we
        try to create it.
        If the App name was passed on the command line instead, we will just
        return with an error if the App wasn't found.
        """
        self.logger.info("Getting app info from the marathon server")
        if self.marathon_config_file:
            try:
                marathon_app_result = marathon_server.get_app(config_file_data["id"])
            except Exception as e:
                self.logger.warn("App doesn't exist %s. Exception is %s" % (config_file_data["id"], e))
                ### App doesn't exist; initialize it
                self.create_marathon_app(marathon_server, config_file_data)
                marathon_app_result = marathon_server.get_app(config_file_data["id"])
        elif self.args.get_app:
            try:
                marathon_app_result = marathon_server.get_app(config_file_data)
            except Exception as e:
                self.logger.warn("App doesn't exist %s. Exception is %s" % (config_file_data, e))
                sys.exit(1)

        self.logger.info(marathon_app_result)
        return marathon_app_result

    def update_marathon_app(self, marathon_server, config_file_data, marathon_app_result):
        """
        Connects to the Marathon Server and sends the App variables. If the
        values have changed, the App will be updated on the server, otherwise
        it makes no changes.
        """
        ### API call to marathon server to update the app if the values have changed
        self.logger.info("Update marathon server with updated app data")
        marathon_server.update_app(config_file_data["id"], marathon_app_result, force=False, minimal=True)

    def create_marathon_app(self, marathon_server, config_file_data):
        """
        Creates the App name on the Marathon Server with minimal default values.
        """
        self.logger.info("App wasn't found. Creating new marathon app")
        self.logger.info(config_file_data["id"])

        ### Initialize app creation and name space
        marathon_server.create_app(config_file_data["id"], MarathonApp(cmd='test', mem=1, cpus=.01))
        self.logger.info("Done creating marathon app.")

    def delete_marathon_app(self, marathon_server, marathon_app):
        """
        Connects to the Marathon Server and issues a delete request.
        """
        self.logger.info("Deleting :")
        self.logger.info(marathon_app)
        marathon_server.delete_app(marathon_app)
        self.logger.info("Marathon app deleted.")

    def run_app(self):
        """
        Creates the Marathon Server connection.
        When using json config files, the tool is used to ensure state of the App.
        If the App doesn't exist, it tries to create it.
        This tool can also be used to delete Apps from Marathon via either a
        json config file or using the App name from the command line.
        """
        marathon_server = MarathonClient("http://" + self.marathon_host + ":" + self.marathon_port)

        ### validate socket connection with given host and port
        self.connect(self.marathon_host, int(self.marathon_port))

        ### list all apps if flag is called
        if self.marathon_list_apps:
            self.list_marathon_apps(marathon_server)

        ### Config file load, only if we passed the variable
        if self.marathon_config_file:
            config_file_data = self.read_config_file(self.marathon_config_file)

            ### get a specific marathon app
            marathon_app_result = self.get_marathon_app(marathon_server, config_file_data)
            self.logger.info(marathon_app_result)

            ### update app data variable with config file values
            self.assign_config_data(config_file_data, marathon_app_result)

            ### update a marathon app
            self.update_marathon_app(marathon_server, config_file_data, marathon_app_result)

        elif self.args.get_app:
            self.logger.info(self.args.get_app)
            marathon_app_result = self.get_marathon_app(marathon_server, self.args.get_app)

        ### Delete marathon app
        if self.args.delete:
            self.delete_marathon_app(marathon_server, marathon_app_result.id)


def main():
    app = MarathonClientApp()
    app.run_app()

# Run the application stand alone
if __name__ == '__main__':
    main()
