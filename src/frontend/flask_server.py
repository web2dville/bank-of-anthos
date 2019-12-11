'''
Copyright 2018 Google LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
'''

import datetime
import json
import logging
import os

from flask import Flask, abort, jsonify, make_response, redirect, \
    render_template, request, url_for

import requests


app = Flask(__name__)
app.config["TRANSACTIONS_URI"] = 'http://{}/new_transaction'.format(
    os.environ.get('TRANSACTIONS_API_ADDR'))
app.config["BALANCES_URI"] = 'http://{}/get_balance'.format(
    os.environ.get('BALANCES_API_ADDR'))
app.config["HISTORY_URI"] = 'http://{}/get_history'.format(
    os.environ.get('HISTORY_API_ADDR'))

TOKEN_NAME = 'token'

local_routing_num = os.getenv('LOCAL_ROUTING_NUM')


# handle requests to the server
@app.route("/home")
def main():
    token = request.cookies.get(TOKEN_NAME)
    if not verify_token(token):
        # user isn't authenticated
        return redirect(url_for('login_page'))

    # get balance
    account_id = token  # TODO: placeholder
    req = requests.get(url=app.config["BALANCES_URI"],
                       params={'account_id': account_id})
    resp = req.json()
    balance = resp['balance']

    # get history
    req = requests.get(url=app.config["HISTORY_URI"],
                       params={'account_id': account_id})
    resp = req.json()
    transaction_list = resp['history']

    # simulate external account data
    external_list = []
    for label, acct, route in [('External Checking', '012345654321', '45678'),
                               ('External Savings', '991235345434', '00101')]:
        external_list += [{'label': label, 'number': acct, 'routing': route}]
    internal_list = []
    for label, number in [('Friend 1', '1111111111'),
                          ('Friend 2', '2222222222')]:
        internal_list += [{'label': label, 'number': number}]
    return render_template('index.html',
                           history=transaction_list,
                           balance=balance,
                           name='Daniel',
                           external_accounts=external_list,
                           favorite_accounts=internal_list)


@app.route('/payment', methods=['POST'])
def payment():
    token = request.cookies.get(TOKEN_NAME)
    if not verify_token(token):
        # user isn't authenticated
        return abort(401)

    account_id = token  # TODO: placeholder
    recipient = request.form['recipient']
    if recipient == 'other':
        recipient = request.form['other-recipient']
    # convert amount to integer
    amount = int(float(request.form['amount']) * 100)
    # verify balance is sufficient
    req = requests.get(url=app.config["BALANCES_URI"],
                       params={'account_id': account_id})
    resp = req.json()
    balance = resp['balance']
    if balance > amount:
        transaction_obj = {'from_routing_num':  local_routing_num,
                           'from_account_num': account_id,
                           'to_routing_num': local_routing_num,
                           'to_account_num': recipient,
                           'amount': amount}
        requests.post(url=app.config["TRANSACTIONS_URI"],
                      data=jsonify(transaction_obj).data,
                      headers={'content-type': 'application/json'},
                      timeout=3)
    return redirect(url_for('main'))


@app.route('/deposit', methods=['POST'])
def deposit():
    token = request.cookies.get(TOKEN_NAME)
    if not verify_token(token):
        # user isn't authenticated
        return abort(401)
    account_id = token  # TODO: placeholder

    # get data from form
    account_details = json.loads(request.form['account'])
    external_account_num = account_details['account_num']
    external_routing_num = account_details['routing_num']
    # convert amount to integer
    amount = int(float(request.form['amount']) * 100)

    # simulate transaction from external bank into user's account
    transaction_obj = {'from_routing_num':  external_routing_num,
                       'from_account_num': external_account_num,
                       'to_routing_num': local_routing_num,
                       'to_account_num': account_id,
                       'amount': amount}
    requests.post(url=app.config["TRANSACTIONS_URI"],
                  data=jsonify(transaction_obj).data,
                  headers={'content-type': 'application/json'},
                  timeout=3)
    return redirect(url_for('main'))


@app.route("/", methods=['GET'])
def login_page():
    token = request.cookies.get(TOKEN_NAME)
    if verify_token(token):
        # already authenticated
        return redirect(url_for('main'))

    return render_template('login.html')


@app.route('/login', methods=['POST'])
def login():
    # username = request.form['username']
    # password = request.form['password']
    resp = make_response(redirect(url_for('main')))
    # set sign in token for 10 seconds
    resp.set_cookie(TOKEN_NAME, '12345', max_age=300)
    return resp


@app.route('/logout', methods=['POST'])
def logout():
    resp = make_response(redirect(url_for('login_page')))
    resp.delete_cookie(TOKEN_NAME)
    return resp


def verify_token(token):
    return token == '12345'


def format_timestamp(timestamp):
    """ Format the input timestamp in a human readable way """
    # TODO: time zones?
    date = datetime.datetime.fromtimestamp(float(timestamp))
    return date.strftime('%b %d, %Y')


def format_currency(int_amount):
    """ Format the input currency in a human readable way """
    amount_str = '${:0,.2f}'.format(abs(float(int_amount)/100))
    if int_amount < 0:
        amount_str = '-' + amount_str
    return amount_str


if __name__ == '__main__':
    for v in ['PORT', 'TRANSACTIONS_API_ADDR', 'BALANCES_API_ADDR',
              'LOCAL_ROUTING_NUM']:
        if os.environ.get(v) is None:
            print("error: {} environment variable not set".format(v))
            exit(1)
    logging.basicConfig(level=logging.INFO,
                        format=('%(levelname)s|%(asctime)s'
                                '|%(pathname)s|%(lineno)d| %(message)s'),
                        datefmt='%Y-%m-%dT%H:%M:%S',
                        )
    logging.getLogger().setLevel(logging.INFO)

    # register format_duration for use in html template
    app.jinja_env.globals.update(format_timestamp=format_timestamp)
    app.jinja_env.globals.update(format_currency=format_currency)

    logging.info("Starting flask.")
    app.run(debug=False, port=os.environ.get('PORT'), host='0.0.0.0')
