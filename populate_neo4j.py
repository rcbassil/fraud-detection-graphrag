import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

uri = os.getenv("NEO4J_URI")
username = os.getenv("NEO4J_USERNAME")
password = os.getenv("NEO4J_PASSWORD")
driver = GraphDatabase.driver(uri, auth=(username, password))

def create_fraud_test_data(tx):
    # Create Players, Terminals, and shared identifiers
    tx.run("""
    // Create Entities
    MERGE (p1:Player {id: 'PLR-001', name: 'John Doe', historical_avg: 50})
    MERGE (p2:Player {id: 'PLR-002', name: 'Jane Smith', historical_avg: 45})
    MERGE (t1:Terminal {id: 'TM-99', location: 'Casino Floor A'})
    MERGE (ip:IPAddress {address: '192.168.1.50'})
    MERGE (addr:Address {street: '123 Multi-Agent Way'})

    // Create Relationships (Collusion Pattern)
    MERGE (p1)-[:LOGGED_IN_FROM]->(ip)
    MERGE (p2)-[:LOGGED_IN_FROM]->(ip)
    MERGE (p1)-[:LIVES_AT]->(addr)
    MERGE (p2)-[:LIVES_AT]->(addr)
    MERGE (p1)-[:PLACED_BET {amount: 5000, timestamp: datetime()}]->(t1)
    MERGE (p2)-[:PLACED_BET {amount: 4800, timestamp: datetime()}]->(t1)
    """)

with driver.session() as session:
    session.execute_write(create_fraud_test_data)
driver.close()