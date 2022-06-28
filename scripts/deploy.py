from functools import partialmethod
from pathlib import Path
from pdb import pm
import yaml
import click
import os
from brownie import interface, config, accounts, Contract, project, FtmStrategy, GenericAaveV3, network, web3
from eth_utils import is_checksum_address

yearnDep = config["dependencies"][0]
Vault = project.load(yearnDep).Vault

acct = accounts.load("yd")

dev = acct
token = Contract("0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83")
gov = "0x72a34AbafAB09b15E7191822A679f28E067C4a16"
rewards = "0x89716Ad7EDC3be3B35695789C475F3e7A3Deb12a"
registry = Contract("0x727fe1759430df13655ddb0731dE0D0FDE929b04")
vault = Vault.at("0x27cbf0fddb356a2d1EBdef604Cfa90F8f300d34E")
strategy = None

param = { "from": acct}

def clone_vault():
    print(f"You are using the '{network.show_active()}' network")
    dev = acct
    print(f"You are using: 'dev' [{dev.address}]")
   

    name = input(f"Set description ['{token.name()} yVault']: ") or ""
    symbol = input(f"Set symbol ['yv{token.symbol()}']: ") or ""
    print(
        f"""
    Vault Parameters
     token: {token.address}
  governer: {gov}
   rewards: {rewards}
      name: '{token.name() + 'yVault'}'
    symbol: '{'yv' + token.symbol()}'
    """
    )
    if input("Deploy New Vault? y/[N]: ").lower() != "y":
        return
    print("Cloning Vault...")
    tx = registry.newExperimentalVault(
        token,
        gov,
        gov,
        rewards,
        name,
        symbol,
        param
    )
    global vault 
    vault = Vault.at(tx.return_value)
    print(f"Vault Cloned to {vault.address}")

    

def clone_strat():
    if input(f"Clone New Strategy for vault at {vault.address}? y/[N]: ").lower() != "y":
        return

    print("Cloning the Gen Lender base strategy")
    to_clone = FtmStrategy.at("0xDf262B43bea0ACd0dD5832cf2422e0c9b2C539dc")
    tx = to_clone.clone(
        vault.address,
        gov,
        rewards,
        gov,
        param)

    global strategy
    strategy = FtmStrategy.at(tx.return_value)
    print(f"Strategy cloned to {strategy.address}")
  
    
def deploy_v3():
    if input(f"Deploy New plugin for Strategy at {strategy.address}? y/[N]: ").lower() != "y":
        return

    print("Deploying new Aave V3 Gen Lender...")
    router = "0xF491e7B69E4244ad4002BC14e878a34207E38c29" #spooky
    router2 = "0x16327E3FbDaCA3bcF7E38F5Af2599D2DDc33aE52" #spirit swap
    name = "AaveV3GenLender"
    
    v3 = GenericAaveV3.deploy(
        strategy.address,
        token, #Wnative is want
        router,
        router2,
        name,
        False,
        param,
        publish_source=True
    )

    print(f"V3 deployed to {v3.address}")



def main():
    #print(project.load(yearnDep))
    #global dev
    #dev = accounts.load(click.prompt("Account", type=click.Choice(accounts.load())))
    print(f"You are using: 'dev' [{dev.address}]")

    print("Cloning Vault")
    #clone_vault()
    clone_strat()
    deploy_v3()
