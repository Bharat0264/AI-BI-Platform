"""Provision/reset an account without accepting passwords in command-line arguments."""
import argparse
from getpass import getpass
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dotenv import load_dotenv
from authentication import auth_database,normalize_username,provision_user


def main():
    load_dotenv()
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--username',required=True);parser.add_argument('--disable',action='store_true');args=parser.parse_args()
    try:
        username=normalize_username(args.username)
        if args.disable:
            db=auth_database();user=db.users.find_one({'username':username})
            if not user:raise ValueError('Account does not exist.')
            db.users.update_one({'user_id':user['user_id']},{'$set':{'disabled':True}})
            db.sessions.delete_many({'user_id':user['user_id']});print('Account disabled; sessions revoked.');return
        password=getpass('Password (at least 12 characters): ')
        if password != getpass('Repeat password: '):raise ValueError('Passwords do not match.')
        provision_user(username,password);print('Account provisioned; earlier sessions revoked.')
    except ValueError as error:raise SystemExit(str(error)) from None


if __name__=='__main__':main()
