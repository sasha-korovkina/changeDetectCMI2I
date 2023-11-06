#!/usr/bin/python3

from changedetectionio import queuedWatchMetaData
from copy import deepcopy
from distutils.util import strtobool
from feedgen.feed import FeedGenerator
from flask_compress import Compress as FlaskCompress
from flask_login import current_user
from flask_restful import abort, Api
from flask_wtf import CSRFProtect
from functools import wraps
from threading import Event
import datetime
import flask_login
import logging
import os
import pytz
import queue
import threading
import time
import timeago

from flask import (
    Flask,
    abort,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)

from flask_paginate import Pagination, get_page_parameter

from changedetectionio import html_tools
from changedetectionio.api import api_v1

__version__ = '0.45.5'

from changedetectionio.store import BASE_URL_NOT_SET_TEXT

datastore = None

# Local
running_update_threads = []
ticker_thread = None

extra_stylesheets = []

update_q = queue.PriorityQueue()
notification_q = queue.Queue()

app = Flask(__name__,
            static_url_path="",
            static_folder="static",
            template_folder="templates")

# Super handy for compressing large BrowserSteps responses and others
FlaskCompress(app)

# Stop browser caching of assets
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

app.config.exit = Event()

app.config['NEW_VERSION_AVAILABLE'] = False

if os.getenv('FLASK_SERVER_NAME'):
    app.config['SERVER_NAME'] = os.getenv('FLASK_SERVER_NAME')

#app.config["EXPLAIN_TEMPLATE_LOADING"] = True

# Disables caching of the templates
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.add_extension('jinja2.ext.loopcontrols')
csrf = CSRFProtect()
csrf.init_app(app)
notification_debug_log=[]

watch_api = Api(app, decorators=[csrf.exempt])


def preview_page(uuid):
    print('App formation starting...')
    global datastore

    # so far just for read-only via tests, but this will be moved eventually to be the main source
    # (instead of the global var)
    print(uuid)
    content = []
    ignored_line_numbers = []
    trigger_line_numbers = []

    # try:
    #     watch = datastore.data['watching'][uuid]
    # except KeyError:
    #     flash("No history found for the specified link, bad link?", "error")
    #     return redirect(url_for('index'))

    system_uses_webdriver = datastore.data['settings']['application']['fetch_backend'] == 'html_webdriver'
    extra_stylesheets = [url_for('static_content', group='styles', filename='diff.css')]


    is_html_webdriver = False
    if (watch.get('fetch_backend') == 'system' and system_uses_webdriver) or watch.get('fetch_backend') == 'html_webdriver':
        is_html_webdriver = True

    # Never requested successfully, but we detected a fetch error
    if datastore.data['watching'][uuid].history_n == 0 and (watch.get_error_text() or watch.get_error_snapshot()):
        flash("Preview unavailable - No fetch/check completed or triggers not reached", "error")
        output = render_template("preview.html",
                                 content=content,
                                 history_n=watch.history_n,
                                 extra_stylesheets=extra_stylesheets,
#                                     current_diff_url=watch['url'],
                                 watch=watch,
                                 uuid=uuid,
                                 is_html_webdriver=is_html_webdriver,
                                 last_error=watch['last_error'],
                                 last_error_text=watch.get_error_text(),
                                 last_error_screenshot=watch.get_error_snapshot())
        print(content)
        return output

    timestamp = list(watch.history.keys())[-1]
    try:
        tmp = watch.get_history_snapshot(timestamp).splitlines()

        # Get what needs to be highlighted
        ignore_rules = watch.get('ignore_text', []) + datastore.data['settings']['application']['global_ignore_text']

        # .readlines will keep the \n, but we will parse it here again, in the future tidy this up
        ignored_line_numbers = html_tools.strip_ignore_text(content="\n".join(tmp),
                                                            wordlist=ignore_rules,
                                                            mode='line numbers'
                                                            )

        trigger_line_numbers = html_tools.strip_ignore_text(content="\n".join(tmp),
                                                            wordlist=watch['trigger_text'],
                                                            mode='line numbers'
                                                            )
        # Prepare the classes and lines used in the template
        i=0
        for l in tmp:
            classes=[]
            i+=1
            if i in ignored_line_numbers:
                classes.append('ignored')
            if i in trigger_line_numbers:
                classes.append('triggered')
            content.append({'line': l, 'classes': ' '.join(classes)})

    except Exception as e:
        content.append({'line': f"File doesnt exist or unable to read timestamp {timestamp}", 'classes': ''})

    output = render_template("preview.html",
                             content=content,
                             history_n=watch.history_n,
                             extra_stylesheets=extra_stylesheets,
                             ignored_line_numbers=ignored_line_numbers,
                             triggered_line_numbers=trigger_line_numbers,
                             current_diff_url=watch['url'],
                             screenshot=watch.get_screenshot(),
                             watch=watch,
                             uuid=uuid,
                             is_html_webdriver=is_html_webdriver,
                             last_error=watch['last_error'],
                             last_error_text=watch.get_error_text(),
                             last_error_screenshot=watch.get_error_snapshot())
    print(output)
    return output

preview_page('f8be2190-6c38-4a52-b93b-9edeb5f361a2')