# dependencies: flask psycopg2_binary

import re
import json
import sys
import time
import email
import argparse
import requests
import imapclient
from vanna import ApiKey
from vanna.remote import VannaDefault
from vanna.flask import VannaFlaskApp


def to_timestamp(stime: str):
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    ss = stime.split(',')[1].strip().split(' ')
    st = "%s-%s-%s %s" % (ss[2], "{:>02}".format(months.index(ss[1]) + 1), "{:>02}".format(int(ss[0])), ss[3])
    return int(time.mktime(time.strptime(st, '%Y-%m-%d %H:%M:%S')) * 1000)


def get_authenticated_credentials(username: str, password: str, open_ssl: bool = False, time_after: int = -1):
    imap = imapclient.IMAPClient('imap.{}'.format(username.split('@')[1]), ssl=open_ssl)
    imap.login(username, password)
    imap.select_folder('INBOX', readonly=True)
    ids = imap.search()
    number = 10  # len(ids)
    standard = 'RFC822'
    for index in range(number):
        uid = ids[-index - 1]
        data = imap.fetch(uid, '({})'.format(standard))
        message = email.message_from_bytes(data[uid][standard.encode()])
        sender = message['From']
        # subject = message['Subject']
        recv_time = to_timestamp(message['Received'].split(';')[-1])
        # print({"subject": subject, "sender": sender, "time": recv_time})
        if sender == 'vanna@vanna.ai':
            if 0 < time_after <= recv_time:
                return re.search(r'>[0-9A-Za-z]{6}<', message.as_string())[0][1:-1]
            else:
                return None
    return None


def get_vanna_apikey(mail_address: str, password: str, pull_interval: float = 3):
    vanna_auth_url = "https://ask.vanna.ai/unauthenticated_rpc"
    vanna_auth_header = {"Content-Type": "application/json"}
    t0 = int(time.time() * 1000 - 3 * 60 * 1000)
    requests.post(vanna_auth_url, headers=vanna_auth_header, data=json.dumps(
        {"method": 'send_otp', "params": [{'email': mail_address}]}))
    while True:
        time.sleep(pull_interval)
        otp_code = get_authenticated_credentials(mail_address, password, time_after=t0)
        if otp_code is not None:
            break
    print("Mail :", mail_address, "Code :", otp_code)
    resp = requests.post(vanna_auth_url, headers=vanna_auth_header, data=json.dumps(
        {"method": 'verify_otp', "params": [{'email': mail_address, 'otp': otp_code}]}))
    if resp.status_code == 200 and resp.json()["result"] is None:
        raise Exception('Please try again ...')
    # print(resp.status_code)
    # print(resp.text)
    return ApiKey(**resp.json()["result"]).key


def parse_argv():
    argv = sys.argv
    parser = argparse.ArgumentParser(usage="{} [options]".format(argv[0]))
    parser.add_argument('-E', '--email', required=True, type=str, help='输入文件路径')
    parser.add_argument('-P', '--password', required=True, type=str, default='output.txt', help='输出文件路径')
    return parser.parse_args()


def main():
    args = parse_argv()
    print("Please wait ...")
    apikey = get_vanna_apikey(args.email, args.password)
    print("Apikey :", apikey)
    vn = VannaDefault(model='chinook', api_key=apikey)
    # For test
    vn.connect_to_postgres("localhost", "department", "postgres", "123dev", port=5432)
    # vn.connect_to_sqlite('Chinook.sqlite')
    # r = vn.ask('所有daily_report数据', visualize=False)
    # print(r)
    VannaFlaskApp(vn).run()


if __name__ == '__main__':
    main()
