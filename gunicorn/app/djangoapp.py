# -*- coding: utf-8 -
#
# This file is part of gunicorn released under the MIT license. 
# See the NOTICE for more information.

import logging
import os
import sys
import traceback

from gunicorn.config import Config
from gunicorn.app.base import Application

class DjangoApplication(Application):
    
    def init_with_file(self, file_name):
        file_name = os.path.abspath(os.path.normpath(file_name))

        if not os.path.exists(file_name):
            return False

        basename = os.path.basename(file_name)
        self.project_path = os.path.dirname(file_name)
        self.settings_modname = "%s.%s" % (os.path.split(self.project_path)[-1], os.path.splitext(basename)[0])
        self.cfg.set("default_proc_name", self.settings_modname)

        sys.path.insert(0, self.project_path)
        sys.path.append(os.path.join(self.project_path, os.pardir))
        return True

    def init_with_module(self, module_name):
        from django.core.management import setup_environ
        try:
            __import__(module_name)
            setup_environ(sys.modules[module_name])
            self.settings_modname = module_name
            return True
        except:
            return False

    def init(self, parser, opts, args):
        from django.conf import ENVIRONMENT_VARIABLE

        # Look for a valid settings specification, in this order :
        #   With command line arguments specified:
        #     - filename from command line
        #     - settings module from command line
        #   Without command line arguments:
        #     - settings.py in the current folder
        #     - settings module in DJANGO_SETTINGS_MODULE env var
        
        search = lambda: False
        if args:
            search = lambda: self.init_with_file(args[0]) or self.init_with_module(args[0])
            error = "Error: Cannot find settings file or module '%s'" % args[0]
        else:
            search = lambda: self.init_with_file("settings.py") or \
                        ( ENVIRONMENT_VARIABLE in os.environ and \
                            self.init_with_module(os.environ[ENVIRONMENT_VARIABLE]) )
            error = "Error: No settings file found in the current directory, and mising or invalid $%s" % ENVIRONMENT_VARIABLE

        if not search():
            sys.stderr.write(error)
            sys.stderr.flush()
            sys.exit(1)
        

    def load(self):
        from django.conf import ENVIRONMENT_VARIABLE
        from django.core.handlers.wsgi import WSGIHandler
        os.environ[ENVIRONMENT_VARIABLE] = self.settings_modname
        return WSGIHandler()

class DjangoApplicationCommand(Application):
    
    def __init__(self, options, admin_media_path):
        self.log = logging.getLogger(__name__)
        self.usage = None
        self.cfg = None
        self.config_file = options.get("config") or ""
        self.options = options
        self.admin_media_path = admin_media_path
        self.callable = None
        self.load_config()

    def load_config(self):
        self.cfg = Config()
        
        if self.config_file and os.path.exists(self.config_file):
            cfg = {
                "__builtins__": __builtins__,
                "__name__": "__config__",
                "__file__": self.config_file,
                "__doc__": None,
                "__package__": None
            }
            try:
                execfile(self.config_file, cfg, cfg)
            except Exception, e:
                print "Failed to read config file: %s" % self.config_file
                traceback.print_exc()
                sys.exit(1)
        
            for k, v in list(cfg.items()):
                # Ignore unknown names
                if k not in self.cfg.settings:
                    continue
                try:
                    self.cfg.set(k.lower(), v)
                except:
                    sys.stderr.write("Invalid value for %s: %s\n\n" % (k, v))
                    raise
        
        for k, v in list(self.options.items()):
            if k.lower() in self.cfg.settings and v is not None:
                self.cfg.set(k.lower(), v)
        
    def load(self):
        from django.core.servers.basehttp import AdminMediaHandler, WSGIServerException
        from django.core.handlers.wsgi import WSGIHandler
        try:
            return  AdminMediaHandler(WSGIHandler(), self.admin_media_path)
        except WSGIServerException, e:
            # Use helpful error messages instead of ugly tracebacks.
            ERRORS = {
                13: "You don't have permission to access that port.",
                98: "That port is already in use.",
                99: "That IP address can't be assigned-to.",
            }
            try:
                error_text = ERRORS[e.args[0].args[0]]
            except (AttributeError, KeyError):
                error_text = str(e)
            sys.stderr.write(self.style.ERROR("Error: %s" % error_text) + '\n')
            sys.exit(1)
            
def run():
    """\
    The ``gunicorn_django`` command line runner for launching Django
    applications.
    """
    from gunicorn.app.djangoapp import DjangoApplication
    DjangoApplication("%prog [OPTIONS] [SETTINGS_PATH]").run()
