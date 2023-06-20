import os
import rsa
import json
import base64
import requests
import getpass as gp
from uuid import uuid4
from urllib.parse import urlparse

def print_actions():
    tags = '—' * 32

    print(f"""\n{tags}\nActions List:
    (1) View Balance
    (2) Make Transaction
    (3) View History
    (4) View All Transactions
    (5) New Wallet
    (Q) Quit\n{tags}\n""")

def clear():
    if os.name in ("nt", "dos"):
        print("\n" * 1000) 
        os.system("cls")
    else:
        print("\033c", end="")

def view_balance():
    node_address = urlparse(input("Enter node address: ")).netloc
    address = input("Enter public key: ")
    
    try:
        balance = json.loads(requests.post(f"http://{node_address}/wallet/balance", json={"address": address}).content.decode()).get("balance")
        print(f"Balance: {balance} KDC")
    except Exception as e:
        print(e)

def make_transaction():
    # Input data
    node_address = urlparse(input("Enter node address: ")).netloc
    sender_address = input("Enter public key: ")
    sender_private_key = gp.getpass("Enter private key: ")
    recipient_address = input("Enter recipient address: ")
    amount = float(input("Enter amount to transfer: "))
    txid = str(uuid4()).replace("-", "") 
    
    transaction = {
            "sender_address": sender_address,
            "recipient_address": recipient_address,
            "amount": amount,
            "txid": txid
    } 
    
    # Load private key from base64 encoding 
    private_key = rsa.PrivateKey.load_pkcs1(base64.urlsafe_b64decode(sender_private_key))
    
    # Sign
    signature_bytes = rsa.sign(json.dumps(transaction, sort_keys=True).encode(), private_key, "SHA-1")
    
    # Confirm
    confirm = input(f"\nSender Address: {sender_address}\n\nRecipient Address: {recipient_address}\n\nAmount: {amount}\n\nConfirm transaction? (Y/N): ").lower()
    
    if confirm in ("y", "yes"):
        # Check that node exists
        try:
            response = requests.post(f"http://{node_address}/transactions/new", json={"sender_address": sender_address, "recipient_address": recipient_address, "amount": amount, "txid": txid, "signature": base64.urlsafe_b64encode(signature_bytes).decode()})
        except Exception as e:
            print(e)
            print("Error: Invalid node.")
            return
        
        print(response.content.decode())

def view_history():
    node_address = urlparse(input("Enter node address: ")).netloc
    address = input("Enter public key: ")
    tags = '—' * 10
    
    try:
        history = json.loads(requests.post(f"http://{node_address}/wallet/history", json={"address": address}).content.decode()).get("history")
        
        for transaction in history:
            print(f"Sender address: {transaction.get('sender_address')}")
            print(f"Recipient address: {transaction.get('recipient_address')}")
            print(f"Amount: {transaction.get('amount')}")
        
            print(tags)
    except Exception as e:
        print(e)

def view_all_transactions():
    node_address = urlparse(input("Enter node address: ")).netloc
    tags = '—' * 10
    
    try:
        transactions = requests.get(f"http://{node_address}/transactions/posted").json().get("transactions")
        
        for transaction in transactions:
            print(f"Sender address: {transaction.get('sender_address')}")
            print(f"Recipient address: {transaction.get('recipient_address')}")
            print(f"Amount: {transaction.get('amount')}")
        
            print(tags)
    except Exception as e:
        print(e)
    
def new_wallet():
    public_key, private_key = rsa.newkeys(1024)

    # Print keys in base64 urlsafe encode
    print(f"Public key: {base64.urlsafe_b64encode(public_key.save_pkcs1()).decode()}\n")
    print(f"Private key: {base64.urlsafe_b64encode(private_key.save_pkcs1()).decode()}\n")
    print("WARNING: DO NOT LOSE EITHER KEY, THEY CANNOT BE RECOVERED. DO NOT SHARE PRIVATE KEY, STORE IT SOMEWHERE SAFE.")

# Main Loop
clear()
action = None

while action != "q":
    try:
        print_actions()
        action = input("Enter choice: ").lower()
    except KeyboardInterrupt:
        action = "q"

    match action:
        case "1":
            try:
                clear()
                view_balance()
            except KeyboardInterrupt:
                pass

            input("Press return/enter to continue...")
        case "2":
            try:
                clear()
                make_transaction()
            except KeyboardInterrupt:
                pass

            input("Press return/enter to continue...")
        case "3":
            try:
                clear()
                view_history()
            except KeyboardInterrupt:
                pass

            input("Press return/enter to continue...")
 
        case "4":
            try:
                clear()
                view_all_transactions()
            except KeyboardInterrupt:
                pass

            input("Press return/enter to continue...")
        case "5":
            try:
                clear()
                new_wallet()
            except KeyboardInterrupt:
                pass

            input("Press return/enter to continue...")
    
    clear()
