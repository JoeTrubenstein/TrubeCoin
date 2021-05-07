import hashlib
import json
from time import time
from urllib.parse import urlparse
from uuid import uuid4

import requests
from flask import Flask, jsonify, request


class Blockchain:
    def __init__(self):
        self.current_transactions = []
        self.chain = []
        self.nodes = set()

        # This is where we create the genesis block! 
        self.new_block(previous_hash='1', proof=100)

    def new_block(self, proof, previous_hash):

        # Our block structure, with the 5 required fields.
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.current_transactions,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
            'proof': proof,
        }

        self.current_transactions = []
        self.chain.append(block)
        return block  

    def new_transaction(self, sender, recipient, amount):
        self.current_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount,
        })

        return self.last_block['index'] + 1  

    @property
    def last_block(self):
        return self.chain[-1]    

    @staticmethod
    def hash(block):

        # This is where we roll up all the data from our block, and hash it.
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def proof_of_work(self, last_block):
        last_proof = last_block['proof']
        last_hash = self.hash(last_block)

    # This is the brute force part. We count up from 0, and try every number until something works.
        proof = 0
        while self.valid_proof(last_proof, proof, last_hash) is False:
            proof += 1
        return proof

    @staticmethod
    def valid_proof(last_proof, proof, last_hash):
        guess = f'{last_proof}{proof}{last_hash}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()

        # Adjust your mining difficulty here! The more zeroes, the more difficult
        # Be aware that anything above 6 will possibly timeout or crash something
        return guess_hash[:4] == "0000"     


# ---- Below here is the stuff needed for the idea of our blockchain becoming a "distributed ledger." ----   

    # First we can add URLs for other nodes.
    # Make sure you use brackets in the request body, even if it's just one url, like this -
    # {
    # "nodes":["http://0.0.0.0:5001"]
    # }
    def register_node(self, address):

        parsed_url = urlparse(address)
        if parsed_url.netloc:
            self.nodes.add(parsed_url.netloc)
        elif parsed_url.path:
            self.nodes.add(parsed_url.path)
        else:
            raise ValueError('Invalid URL')     

    # Here we make sure our hash values are correct
    def valid_chain(self, chain):

        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            print(f'{last_block}')
            print(f'{block}')
            print("\n-----------\n")

            last_block_hash = self.hash(last_block)
            if block['previous_hash'] != last_block_hash:
                return False

            if not self.valid_proof(last_block['proof'], block['proof'], last_block_hash):
                return False

            last_block = block
            current_index += 1

        return True

    # Here we can find the longest (valid) chain out of all our registered nodes,
    # If it's not ours, we can replace ours with the longer one.
    def resolve_conflicts(self):

        all_nodes = self.nodes
        new_chain = None

        max_length = len(self.chain)

        for node in all_nodes:
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        if new_chain:
            self.chain = new_chain
            return True

        return False


# Fire up the server
app = Flask(__name__)
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False

# This should really be a unique UUID to mimic a cypto wallet address, I'm just having fun.
node_identifier = "Joe's Crypto Wallet'"

# Fire up the whole thing
blockchain = Blockchain()

@app.route('/mine', methods=['GET'])
def mine():
    # This runs our proof of work algorithm defined above, and records how long it takes to brute force a solution
    start_time = time()
    last_block = blockchain.last_block
    proof = blockchain.proof_of_work(last_block)
    elapsed = time() - start_time

    # Pay out some coins for a successful mining session.
    blockchain.new_transaction(
        sender="TrubeCoin Mining Reward",
        recipient=node_identifier,
        amount=3,
    )

    # Add the new block to the chain!
    previous_hash = blockchain.hash(last_block)
    block = blockchain.new_block(proof, previous_hash)

    response = {
        'message': "New Block mined and added to the chain!",
        'index': block['index'],
        'transactions': block['transactions'],
        'previous_hash': block['previous_hash'],
        'the answer was ': block['proof'],
        'seconds required to solve ' : elapsed
    }
    return jsonify(response), 200


@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()

    # Check that the required fields are in the POST'ed data
    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return 'Missing values', 400

    # Create a new Transaction
    index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])

    response = {'message': f'Success! Transaction will be recorded in the next mined block.'}
    return jsonify(response), 201


@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200


@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()

    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400

    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': 'New nodes registered successfully!',
        'total_nodes': list(blockchain.nodes),
    }
    return jsonify(response), 201


@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {
            'message': 'Found a more current chain on a different node. This node has been updated! ',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'This node is already up to date!',
            'chain': blockchain.chain
        }

    return jsonify(response), 200


if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen on')
    args = parser.parse_args()
    port = args.port

    app.run(host='0.0.0.0', port=port)