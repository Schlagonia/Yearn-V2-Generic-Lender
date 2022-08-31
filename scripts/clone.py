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

acct = accounts.load("")

dev = acct
token = None #Contract("0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83")
gov = "0xF5d9D6133b698cE29567a90Ab35CfB874204B3A7"
sms = "0xea3a15df68fCdBE44Fdb0DB675B2b3A14a148b26"
rewards = "0x84654e35E504452769757AAe5a8C7C6599cBf954"
registry = Contract("0x1ba4eB0F44AB82541E56669e18972b0d6037dfE0")
vault = Vault.at("0xa318373f0424ef0257b5b75460548D6d34947D97")
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
    to_clone = OptStrategy.at("0x2e98053f4A1b2595bfaA4d0Ad0a450F8DEb8BBCC")
    tx = to_clone.clone(
        vault.address,
        sms,
        rewards,
        acct,
        param)

    global strategy
    strategy = OptStrategy.at(tx.return_value)
    print(f"Strategy cloned to {strategy.address}")
  
    
def deploy_v3():
    if input(f"Cloning New plugin for Strategy at {strategy.address}? y/[N]: ").lower() != "y":
        return

    print("Deploying new Aave V3 Gen Lender...")
    router = "0xa132dab612db5cb9fc9ac426a0cc215a3423f9c9" #Teledrome
    router2 = "0x0000000000000000000000000000000000000000" #
    name = "AaveV3GenLender"
    
    originalV3 = GenericAaveV3.at("0x4806cf1caD561AC271F64dA86423Ea06255E4e06")
    tx = originalV3.cloneAaveLender(
        strategy.address,
        router,
        router2,
        name,
        True,
        param
    )

    v3 = GenericAaveV3.at(tx.return_value)
    print(f"V3 apr {v3.apr()}")
    print(f"V3 deployed to {v3.address}")


def main():
    print(f"You are using: 'dev' [{dev.address}]")

    print("Cloning Strategy")
    #clone_vault()
    clone_strat()
    deploy_v3()
