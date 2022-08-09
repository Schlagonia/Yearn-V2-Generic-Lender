from functools import partialmethod
from pathlib import Path
from pdb import pm
import yaml
import click
import os
from brownie import interface, config, accounts, Contract, project, Strategy, GenericAaveV3, network, web3
from eth_utils import is_checksum_address

yearnDep = config["dependencies"][0]
Vault = project.load(yearnDep).Vault

acct = accounts.load("yd")

dev = acct
token = Contract("0x4200000000000000000000000000000000000006")
gov = "0xea3a15df68fCdBE44Fdb0DB675B2b3A14a148b26"
rewards = "0x84654e35E504452769757AAe5a8C7C6599cBf954"
registry = Contract("0x1ba4eB0F44AB82541E56669e18972b0d6037dfE0")
vault = Vault.at("0xAcB84e988327D7ACc843d6f1389f99f5f864529a")
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
        acct,
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
    if input(f"Deploying New Strategy for vault at {vault.address}? y/[N]: ").lower() != "y":
        return

    print("Deploying the Gen Lender base strategy")
    global strategy
    #strategy = Strategy.deploy(vault.address, param, publish_source=True)
    #strategy = Strategy.at(tx.return_value)
    strategy = Strategy.at("0xdF43263DFec19117f2Fe79d1D9842a10c7495CcD")
    print(f"Strategy cloned to {strategy.address}")
    """
    vault.addStrategy(
        strategy.address,
        10_000,
        0,
        2 ** 256 - 1,
        0,
        param
    )
    """
    Strategy.publish_source(strategy)

    #vault.setGovernance(gov, param);
    
    
def deploy_v3():
    if input(f"Deploy New plugin for Strategy at {strategy.address}? y/[N]: ").lower() != "y":
        return

    print("Deploying new Aave V3 Gen Lender...")
    router = "0xa132DAB612dB5cB9fC9Ac426A0Cc215A3423F9c9" #Veledrome
    router2 = "0x0000000000000000000000000000000000000000" #
    name = "AaveV3GenLender"
    
    v3 = GenericAaveV3.deploy(
        strategy.address,
        token, #Wnative is want
        router,
        router2,
        name,
        True,
        param,
        publish_source=True
    )

    print(f"V3 deployed to {v3.address}")

    strategy.addLender(v3.address, param)



def main():
    #print(project.load(yearnDep))
    #global dev
    #dev = accounts.load(click.prompt("Account", type=click.Choice(accounts.load())))
    print(f"You are using: 'dev' [{dev.address}]")

    print("Deploying")
    #clone_vault()
    clone_strat()
    #deploy_v3()
