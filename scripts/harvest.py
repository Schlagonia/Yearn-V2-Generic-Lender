from functools import partialmethod
from pathlib import Path
from pdb import pm
import yaml
import click
import os
from brownie import interface, config, accounts, Contract, project, OptStrategy, GenericAaveV3, network, web3
from eth_utils import is_checksum_address

yearnDep = config["dependencies"][0]
Vault = project.load(yearnDep).Vault

acct = accounts.load("yd")

dev = acct
#token = Contract("0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83")
#gov = "0x72a34AbafAB09b15E7191822A679f28E067C4a16"
#rewards = "0x89716Ad7EDC3be3B35695789C475F3e7A3Deb12a"
#registry = Contract("0x727fe1759430df13655ddb0731dE0D0FDE929b04")
#vault = Vault.at("0x27cbf0fddb356a2d1EBdef604Cfa90F8f300d34E")
strategy = OptStrategy.at("0x2e98053f4A1b2595bfaA4d0Ad0a450F8DEb8BBCC") #None

param = { "from": acct}

def harvest_lender():

    print("Harvesting the Gen Lender base strategy")
    strategy.harvest(param)

    print("Harvested plug in")
  
    
def harvest_plugin():

    print("HArvesting new Aave V3 Gen Lender...")
    v3 = GenericAaveV3.at("0x4806cf1caD561AC271F64dA86423Ea06255E4e06")

    v3.harvest(param)

    print(f"Harvested plug in")

def main():
    #print(project.load(yearnDep))
    #global dev
    #dev = accounts.load(click.prompt("Account", type=click.Choice(accounts.load())))
    print(f"You are using: 'dev' [{dev.address}]")

    print("Cloning Vault")
    #clone_vault()
    harvest_plugin()
    harvest_lender()
