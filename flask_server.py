#!/usr/bin/env python3

from functools import wraps
from flask import Flask, render_template, request, Response, jsonify
from flask_socketio import emit
import yaml
import json
import logging

from core.case import Case
from core.judge import TrustedSubmission
from config.config import COMPILE_MAX_TIME_FOR_TRUSTED
from handler import flask_app, socketio, judge_handler, judge_handler_one, generate_handler, validate_handler


@flask_app.route('/reset', methods=['GET', 'POST'])
def reset():
    template_name = "reset.html"
    token_name = 'config/token.yaml'
    with open(token_name) as token_fs:
        tokens = yaml.load(token_fs.read())
    old_password_required = True if tokens['password'] else False
    if request.method == 'GET':
        return render_template(template_name, old_password_required=old_password_required)
    else:
        new_password = request.form.get('new_password')
        if old_password_required and request.form.get('old_password') != tokens['password']:
            return Response("Sorry, bad token!")
        if not new_password:
            return Response("Sorry, password cannot be empty!")
        if new_password != request.form.get('new_password_confirm'):
            return Response("Two passwords do not agree.")
        tokens['password'] = new_password
        with open(token_name, 'w') as token_fs:
            yaml.dump(tokens, token_fs)
        return Response('Reset complete!')


def check_auth(username, password):
    token_name = 'config/token.yaml'
    with open(token_name) as token_fs:
        tokens = yaml.load(token_fs.read())
    return username == tokens['username'] and password == tokens['password']


def authorization_failed():
    return jsonify({'status': 'reject', 'message': 'authorization failed'})


def auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authorization_failed()
        return f(*args, **kwargs)
    return decorated


def response_ok():
    return jsonify({'status': 'received'})


@flask_app.route('/upload/case/<fid>/<io>', methods=['POST'])
@auth_required
def upload_case(fid, io):
    """
    You need to do something like /upload/case/f3758/input and bind binary data to request.data
    """
    case = Case(fid)
    if io == 'input':
        case.write_input_binary(request.data)
    elif io == 'output':
        case.write_output_binary(request.data)
    return response_ok()


@flask_app.route('/upload/checker/<fid>', methods=['POST'])
@flask_app.route('/upload/interactor/<fid>', methods=['POST'])
@auth_required
def upload_trusted_submission(fid):
    data = json.loads(request.get_json())
    program = TrustedSubmission(data['fingerprint'], data['code'], data['lang'], permanent=True)
    program.compile(COMPILE_MAX_TIME_FOR_TRUSTED)
    return response_ok()


@flask_app.route('/delete/case/<fid>', methods=['POST'])
@auth_required
def delete_case(fid):
    case = Case(fid)
    case.clean()
    return response_ok()


@flask_app.route('/delete/checker/<fid>', methods=['POST'])
@flask_app.route('/delete/interactor/<fid>', methods=['POST'])
@auth_required
def delete_trusted_submission(fid):
    'This api is not recommended to use'
    program = TrustedSubmission.fromExistingFingerprint(fid)
    program.clean(True)
    return response_ok()


@flask_app.route('/generate', methods=['POST'])
@auth_required
def generate():
    data = json.loads(request.get_json())
    p = generate_handler.apply_async((data['fingerprint'], data['code'], data['lang'],
                                      data['max_time'], data['max_memory'], data['command_line_args']))
    return jsonify(p.get())


@flask_app.route('/validate', methods=['POST'])
@auth_required
def validate():
    data = json.loads(request.get_json())
    p = validate_handler.apply_async((data['fingerprint'], data['code'], data['lang'],
                                      data['max_time'], data['max_memory'], data['input']))
    return jsonify(p.get())


@flask_app.route('/judge/<target>', methods=['POST'])
@auth_required
def judge_one(target):
    data = json.loads(request.get_json())
    p = judge_handler_one.apply_async((data['submission'], data['max_time'], data['max_memory'], data['input']),
                                      {'case_output_b64': data.get('output'), 'target': target,
                                       'interactor': data.get('interactor'), 'checker': data.get('checker')})
    return jsonify(p.get())


@flask_app.route('/judge', methods=['POST'])
@auth_required
def judge():
    'This is the http version of judge, used in retry'
    def on_raw_message(body):
        logging.info(body)

    data = json.loads(request.get_json())
    p = judge_handler.apply_async((data['fingerprint'], data['code'], data['lang'], data['cases'],
                                   data['max_time'], data['max_memory'], data['checker']),
                                  {'interactor_fingerprint': data.get('interactor'),
                                   'run_until_complete': data.get('run_until_complete', False),})
    return jsonify(p.get(on_message=on_raw_message))


@socketio.on('judge')
def handle_message(data):
    def on_raw_message(body):
        emit('judge_reply', body['result'])

    if not check_auth(data.get('username'), data.get('password')):
        return authorization_failed()
    p = judge_handler.apply_async((data['fingerprint'], data['code'], data['lang'], data['cases'],
                                   data['max_time'], data['max_memory'], data['checker']),
                                  {'interactor_fingerprint': data.get('interactor'),
                                   'run_until_complete': data.get('run_until_complete', False),})
    return jsonify(p.get(on_message=on_raw_message))


if __name__ == '__main__':
    socketio.run(flask_app, host='0.0.0.0', port=5000)
    # flask_app.run(host='0.0.0.0', port=5000, debug=True)