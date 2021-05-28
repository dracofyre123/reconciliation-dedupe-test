#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
This code demonstrates the Gazetteer.

We will use one of the sample files from the RecordLink example as the
canonical set.

This is an unholy merger of 
https://github.com/mblwhoi/reconciliation_service_skeleton
(as cleaned up in https://github.com/BrickSchema/reconciliation-api )
and
https://github.com/dedupeio/dedupe-examples/tree/master/gazetteer_example

"""

import os
import csv
import re
import logging
import optparse
import datetime

import dedupe
from unidecode import unidecode

from flask import Flask, request
from flask_jsonpify import jsonify
import json

import sqlite3
from flask import g

import uuid

app = Flask(__name__)


DATABASE = 'session.db'

default_settings_file = 'gazetteer_learned_settings'
default_training_file = 'gazetteer_training.json'

canonical = None
messy = None


# these are all from the flask docs
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv



metadata = {
    "name": "Example Reconciliation Service",
    "defaultTypes": [
        {"id": "Resturants", "name": "ResturantNames"},
    ]
}


# for the moment only search on name
# TODO: make this more configurable, the protocol is actually pretty cool
# with regards to addtional property types, but it would make the
# testbench web app pretty useless
fields = [
    {'field': 'name', 'type': 'String'},
    #{'field': 'title', 'type': 'Text', 'corpus': descriptions()},
    #{'field': 'addr', 'type': 'String', 'has missing': True},
    #{'field': 'city', 'type': 'String', 'has missing': True},
    #{'field': 'phone', 'type': 'String', 'has missing': True},
    #{'field': 'type', 'type': 'String', 'has missing': True},
]




def preProcess(column):
    """
    Do a little bit of data cleaning with the help of Unidecode and Regex.
    Things like casing, extra spaces, quotes and new lines can be ignored.
    """

    column = unidecode(column)
    column = re.sub('\n', ' ', column)
    column = re.sub('-', '', column)
    column = re.sub('/', ' ', column)
    column = re.sub("'", '', column)
    column = re.sub(",", '', column)
    column = re.sub(":", ' ', column)
    column = re.sub(' +', ' ', column)
    column = column.strip().strip('"').strip("'").lower().strip()
    if not column:
        column = None
    return column


def readData(filename):
    """
    Read in our data from a CSV file and create a dictionary of records,
    where the key is a unique record ID.
    """

    data_d = {}

    with open(filename) as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            clean_row = dict([(k, preProcess(v)) for (k, v) in row.items()])
            data_d[clean_row['id']] = dict(clean_row)

    return data_d



@app.route("/session", methods=["POST"])
def new_sesion():
    cur = get_db().cursor()
    session_id = uuid.uuid4()
    created_time = datetime.datetime.now().isoformat()
    results = cur.execute("INSERT INTO session VALUES(?, ?, ?, ?, ?)", (str(session_id), None, created_time, created_time, 'NEW'))
    cur.close()
    get_db().commit()
    return jsonify({"session_id": str(session_id)})

@app.route("/session/<session_id>", methods=["GET"])
def lookup_session(session_id):
    try:
        valid_uuid_obj = uuid.UUID(session_id, version=4)
    except ValueError:
        return False
    session_info = query_db("SELECT * from session where id = ?", [session_id], one=True)
    return jsonify(session_info)

@app.route("/session/<session_id>/add_training_data", methods=["POST"])
def add_training_data(session_id):
    try:
        valid_uuid_obj = uuid.UUID(session_id, version=4)
    except ValueError:
        return False
    session_id = valid_uuid_obj

    session_info = query_db("SELECT * from session where id = ?", [str(session_id)], one=True)
    old_version_id = session_info[1]

    new_version_id = uuid.uuid4()

    gazetteer = dedupe.Gazetteer(fields)
 
    #k = canonical.keys()
    #k = list(k)[0]
    #one = {k: canonical[k]}

    saved_training_file = None
    if(old_version_id):
        saved_training_file = 'sessions/training_file.{}.json'.format(old_version_id)

    if saved_training_file and os.path.exists(saved_training_file):
        with open(saved_training_file) as tf:
            gazetteer.prepare_training(messy, canonical, tf)
    else:
        gazetteer.prepare_training(messy, canonical)

    content = request.json
    # these need to be actual tuples, I think?
    # TODO: obviously validate more of the request, don't just take raw JSON from the client
    content['match'] = [(x[0], x[1]) for x in content['match']]

    gazetteer.mark_pairs(content)
    gazetteer.train()

    new_training_file = 'sessions/training_file.{}.json'.format(str(new_version_id))
    with open(new_training_file, 'w') as tf:
        gazetteer.write_training(tf)
    
    new_settings_file = 'sessions/learned_settings_file.{}'.format(str(new_version_id))
    with open(new_settings_file, 'wb') as sf:
            gazetteer.write_settings(sf)
    
    gazetteer.cleanup_training()

    cur = get_db().cursor()
    updated_time = datetime.datetime.now().isoformat()
    try:
        results = cur.execute("UPDATE session SET currentversion = ?, updated_date = ?, status = 'TRAINED' where id = ?", (str(new_version_id), updated_time, str(session_id)))
        get_db().commit()
    except sqlite3.Error as e:
        print(e)
        return False


    return jsonify({"session_id": str(session_id), "version_id": str(new_version_id), "old_version_id": old_version_id})

def resolve(q, gazetteer):
    """
    q has fields:
    - query: string of the label that needs to be converted to a Brick type
    - type: optional list of 'types' (e.g. "PointClass" above)
    - limit: optional limit on # of returned candidates (default to 10)
    - properties: optional map of property idents to values
    - type_strict: [any, all, should] for strictness on the types returned
    """
    limit = int(q.get('limit', 10))

    query = q.get('query', '')
    res = []
    target = {"target": {"name": query, "addr": None, "city": None, "phone": None, "type": None}}

    results = gazetteer.search(target, n_matches=limit, generator=True)

    for cluster_id, (messy_id, matches) in enumerate(results):

        for canon_id, score in matches:
            #print("matching {} to {}".format(messy_id, canon_id))

            res.append({
                'id': canon_id,
                'name': canonical[canon_id]["name"],
                'score': float(score),
                'match': True,
                'type': [{"id": "Resturants", "name": "ResturantNames"}],
            })
    return res


@app.route("/reconcile", methods=["POST", "GET"])
def reconcile():

    if request.method == "GET":
        queries = json.loads(request.args.get("queries", "[]"))
        session_id = request.args.get("session", None)
    else:
        queries = json.loads(request.form.get("queries", "[]"))
        session_id = request.form.get("session", None)

    # look for a new/nonstandard property in the form/params for session
    version_id = None
    if session_id:
        try:
            valid_uuid_obj = uuid.UUID(session_id, version=4)
        except ValueError:
            return False
        # normalize the sessionid for caps (ab123-xxx vs AB123-)
        session_id = str(valid_uuid_obj)
        session_info = query_db("SELECT * from session where id = ?", [str(session_id)], one=True)
        version_id = session_info[1]
        if session_info[4] == "NEW":
            print("WARNING: session has not yet added training data, version_id is {} so default training session will be used".format(version_id))
    
    
    if queries:
        settings_file = default_settings_file
        if version_id:
            # demoware so we don't care about security
            # also because they're UUIDs for now just treat the version_ids as distinct
            # though it really should be sesssion_id.version_id as the filename extension
            session_settings_file = 'sessions/learned_settings_file.{}'.format(version_id)
            if os.path.exists(session_settings_file):
                settings_file = session_settings_file

        with open(settings_file, 'rb') as sf:
            gazetteer = dedupe.StaticGazetteer(sf)

        gazetteer.index(canonical)

        results = {}
        for qid, q in queries.items():
            results[qid] = {'result': resolve(q, gazetteer)}
        return jsonify(results)
    # if no queries, then return the manifest
    return jsonify(metadata)


if __name__ == '__main__':

    # ## Logging

    # dedupe uses Python logging to show or suppress verbose output. Added
    # for convenience.  To enable verbose logging, run `python
    # examples/csv_example/csv_example.py -v`
    optp = optparse.OptionParser()
    optp.add_option('-v', '--verbose', dest='verbose', action='count',
                    help='Increase verbosity (specify multiple times for more)'
                    )
    (opts, args) = optp.parse_args()
    log_level = logging.WARNING
    if opts.verbose:
        if opts.verbose == 1:
            log_level = logging.INFO
        elif opts.verbose >= 2:
            log_level = logging.DEBUG
    logging.getLogger().setLevel(log_level)

    # ## Setup

    canon_file = os.path.join('restaurants', 'fodors.csv')
    messy_file = os.path.join('restaurants', 'zagats.csv')

    # TODO: the gazetteer interface wants a file of candidate records
    # to match against - the "messy" file that it's trying to match 
    # against the "canonical" file. You don't need that if you've already
    # trained, but if you're going to train again -even retraining - you
    # need to have a file of candidate "messy" records when you create the
    # gazetteer object. What we should do is convert the uploaded examples
    # to the "messy" file and use those, but for now we'll just hack it and
    # give the gazetteer object a full dataset
    messy = readData(messy_file)
    print('N data 1 records: {}'.format(len(messy)))

    canonical = readData(canon_file)
    print('N data 2 records: {}'.format(len(canonical)))

    app.run()