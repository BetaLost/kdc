import rsa
import json
import base64
import hashlib
import requests
import threading
from time import time
from uuid import uuid4
from urllib.parse import urlparse
from flask import Flask, jsonify, request

class Blockchain:
    def __init__(self):
        # Declare variables
        self.nodes = set()
        self.pending_transactions = []
        self.chain = []
        
        # Genesis block
        self.create_block(0, True)
    
    def create_block(self, nonce, genesis=False):
        if genesis:
            previous_hash = "0"
        else:
            previous_hash = self.hash_block(self.chain[-1])
        
        block = {
            "index": len(self.chain) + 1,
            "timestamp": time(),
            "transactions": self.pending_transactions,
            "nonce": nonce,
            "previous_hash": previous_hash
        }

        # Clear transactions added to block
        self.pending_transactions = []

        self.chain.append(block)
        return block

    def submit_transaction(self, sender_address, recipient_address, amount, txid, signature):
        transaction = {
            "sender_address": sender_address,
            "recipient_address": recipient_address,
            "amount": amount,
            "txid": txid
        }
        
        # Reward for mining a block
        if sender_address == "Mining Reward":
            self.pending_transactions.append(transaction)
        # Transfer from wallet to wallet
        else:
            # Confirm that the sender has the amount to transfer
            sender_balance = self.get_balance(sender_address)
            
            if sender_balance < amount:
                return False

            # Check that the transaction is signed with an authentic private key
            try:
                # Decode sender address using urlsafe base64 then load the public key
                sender_public_key = rsa.PublicKey.load_pkcs1(base64.urlsafe_b64decode(sender_address))
                signature_bytes = base64.urlsafe_b64decode(signature)
                
                # If the signature is verified, append the transaction
                if rsa.verify(json.dumps(transaction, sort_keys=True).encode(), signature_bytes, sender_public_key) == "SHA-1":
                    self.pending_transactions.append(transaction)
                    
                    # Return the index of the block where the transaction will be posted
                    return len(self.chain) + 1
            except:
                return False
    
    def proof_of_work(self):
        last_block = self.chain[-1]
        previous_nonce = last_block.get("nonce")
        previous_hash = self.hash_block(last_block)
        
        nonce = 0

        # Keep iterating until the puzzle is solved
        while not self.valid_nonce(previous_nonce, previous_hash, nonce):
            nonce += 1
        
        return nonce
    
    def valid_chain(self, chain):
        previous_block = chain[0]
        current_index = 1
        
        # Loop through entire chain and validate consecutive blocks
        while current_index < len(chain):
            current_block = chain[current_index]
            
            # Validate index
            if previous_block.get("index") > current_block.get("index"):
                return False
            
            # Validate timestamp
            if previous_block.get("timestamp") > current_block.get("timestamp"):
                return False
            
            # Validate hash
            if current_block.get("previous_hash") != self.hash_block(previous_block):
                return False
            
            # Validate nonce
            if not self.valid_nonce(previous_block.get("nonce"), current_block.get("previous_hash"), current_block.get("nonce")):
                return False
            
            # Move on to next block
            previous_block = current_block
            current_index += 1
        
        return True
    
    def resolve_chain(self):
        # Return True if the Consensus Algorithm replaces current chain with a longer one, else return False
        
        # Declare Variables
        new_chain = None
        current_length = len(self.chain)

        # Loop through all nodes to see if there is a longer chain
        for node in self.nodes:
            # Get peer's chain
            try:
                response = requests.get(f"http://{node}/chain")
            except:
                self.nodes.remove(node)
                continue

            # Response data
            length = response.json().get("length")
            chain = response.json().get("chain")

            # Store peer's chain if it is longer and valid
            if length > current_length and self.valid_chain(chain):
                current_length = length
                new_chain = chain
        
        # Replace current chain if a longer chain was found, clear pending transactions that are already posted
        if new_chain:
            self.chain = new_chain
            self.pending_transactions = []
            return True
        
        return False
    
    def get_transactions(self):
        transactions = []

        for block in self.chain:
            for transaction in block.get("transactions"):
                transactions.append(transaction)
        
        return transactions
    
    def get_balance(self, address):
        transactions = self.get_transactions()
        balance = 0
        
        for transaction in transactions:
            if transaction.get("recipient_address") == address:
                balance += transaction.get("amount")
            elif transaction.get("sender_address") == address:
                balance -= transaction.get("amount")
        
        return balance


    @staticmethod
    def hash_block(block):
        # Store block as string then return SHA256 hash
        block_string = json.dumps(block, sort_keys=True)
        return hashlib.sha256(block_string.encode()).hexdigest()
    
    @staticmethod
    def valid_nonce(previous_nonce, previous_hash, new_nonce):
        # Concatenate previous nonce, previous hash, and new nonce then hash them
        attempt = f"{previous_nonce}{previous_hash}{new_nonce}".encode()
        attempt_hash = hashlib.sha256(attempt).hexdigest()

        # Check if the proof is valid or not, hash must begin with 1125
        return attempt_hash[:4] == "1125"
    

# Instantiate blockchain
blockchain = Blockchain()

# Start node
app = Flask(__name__)

@app.route("/nodes/register", methods=["POST"])
def register_nodes():
    # Store nodes passed (if any)
    node_address = request.get_json().get("node_address")

    # Return error if no address was passed
    if node_address is None:
        return "Error: Did not supply a valid address", 400

    # Check for correct format
    node_address = urlparse(node_address).netloc
    
    if not node_address:
        return "Error: Invalid format.", 400

    # Check if node exists
    try:
        requests.get(f"http://{node_address}/nodes/get")
    except:
        return "Error: Failed to contact node.", 400
    
    # Register node
    blockchain.nodes.add(node_address)
    
    # Loop through peers then send missing nodes
    for peer in blockchain.nodes:
        # Check if peer is still online
        try:
            registered_nodes = requests.get(f"http://{peer}/nodes/get").json().get("nodes")
            
            for node in blockchain.nodes:
                if node in registered_nodes:
                    continue
                
                requests.post(f"http://{peer}/nodes/register", json={"node_address": f"http://{node}"})
        except:
            # Remove peer address if no longer online
            blockchain.nodes.remove(peer)
    
    # Return response
    response = {
        "message": f"Registered node at: {node_address}.",
        "nodes": list(blockchain.nodes)
    }
    
    return jsonify(response), 201

@app.route("/nodes/get", methods=["GET"])
def get_nodes():
    response = {
        "nodes": list(blockchain.nodes)
    }
    
    return jsonify(response), 200

@app.route("/nodes/resolve", methods=["GET"])
def consensus():
    # Value is True if chain was replaced, otherwise value is False
    replaced = blockchain.resolve_chain()

    # Return response
    if replaced:
        response = {
            "message": "Chain was replaced.",
            "new_chain": blockchain.chain
        }
    else:
        response = {
            "message": "Chain was not replaced, current chain is the longest.",
            "chain": blockchain.chain
        }
    
    return jsonify(response), 200

@app.route("/wallet/history", methods=["POST"])
def wallet_history():
    address = request.get_json().get("address")
    
    if address == None:
        return "Error: No address supplied.", 400
    
    transactions = blockchain.get_transactions()
    history = []
    
    for transaction in transactions:
        if (transaction.get("sender_address") == address) or (transaction.get("recipient_address") == address):
            history.append(transaction)
    
    response = {
        "history": history
    }
    
    return jsonify(response), 200

@app.route("/wallet/balance", methods=["POST"])
def get_balance():
    address = request.get_json().get("address")
    
    if address == None:
        return "Error: No address supplied.", 400
 
    response = {
        "balance": blockchain.get_balance(address)
    }
    
    return jsonify(response), 200


@app.route("/transactions/new", methods=["POST"])
def new_transaction():
    # Store POST request parameters
    values = request.get_json()
    
    # Check that all required parameters were passed
    if not all(value in values for value in ["sender_address", "recipient_address", "amount", "txid", "signature"]):
        return "Error: Missing parameters.", 400
    
    sender_address = values.get("sender_address")
    recipient_address = values.get("recipient_address")
    amount = values.get("amount")
    txid = values.get("txid")
    signature = values.get("signature")
    
    transaction = {
        "sender_address": sender_address,
        "recipient_address": recipient_address,
        "amount": amount,
        "txid": txid
    } 
    
    # Create new transaction
    output = blockchain.submit_transaction(sender_address, recipient_address, amount, txid, signature)
    
    # Return error
    if output == False:
        return "Error: Invalid request.", 400
    
    # Broadcast transaction to all known peers
    for peer in blockchain.nodes:
        # Check if peer is still online
        try:
            pending_transactions = requests.get(f"http://{peer}/transactions/pending").json().get("transactions")
            
            if not (transaction in pending_transactions):
                requests.post(f"http://{peer}/transactions/new", json={"sender_address": sender_address, "recipient_address": recipient_address, "amount": amount, "txid": txid, "signature": signature})
        except:
            # Remove peer address if no longer online
            blockchain.nodes.remove(peer)

    response = {"message": f"Transaction will be posted to Block {output}."}
    return jsonify(response), 201

@app.route("/transactions/posted", methods=["GET"])
def get_posted_transactions():

    response = {
         "transactions": blockchain.get_transactions()
     }
     
    return jsonify(response), 200

@app.route("/transactions/pending", methods=["GET"])
def get_pending_transactions():

    response = {
         "transactions": blockchain.pending_transactions
     }
     
    return jsonify(response), 200


@app.route("/chain", methods=["GET"])
def get_chain():
    response = {
        "chain": blockchain.chain,
        "length": len(blockchain.chain)
    }
    
    return jsonify(response), 200

@app.route("/mine", methods=["GET"])
def mine():
    # Find new nonce
    nonce = blockchain.proof_of_work()
    
    # Reward 1 KDC for finding new proof
    txid = str(uuid4()).replace("-", "") 
    blockchain.submit_transaction("Mining Reward", reward_address, 1, txid, None)
    
    # Forge new block
    block = blockchain.create_block(nonce)
    
    # Force registered nodes to resolve chain
    for node in blockchain.nodes:
        try:
            requests.get(f"http://{node}/nodes/resolve")
        except:
            blockchain.nodes.remove(node)
    
    # Return response
    response = {
        "message": "Forged new block",
        "block_index": block.get("index"),
        "block_transactions": block.get("transactions"),
        "block_nonce": block.get("nonce"),
        "previous_hash": block.get("previous_hash")
    }
    
    return jsonify(response), 200

if __name__ == "__main__":
    port = int(input("Enter port: "))
    reward_address = input("Address for reward: ")
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False)).start()
    blockchain.nodes.add(f"127.0.0.1:{port}")
    
    try:
        node_address = urlparse(input("Enter address of an active node: ")).netloc
        requests.post(f"http://{node_address}/nodes/register", json={"node_address": f"http://127.0.0.1:{port}"}) 
    except:
        pass
    
    while True:
        input("Press return/enter to mine next block...")
        requests.get(f"http://127.0.0.1:{port}/mine") 

    
