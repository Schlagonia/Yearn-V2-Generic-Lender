from pathlib import Path
from pdb import pm
import yaml
import click

from brownie import interface, config, accounts, network, web3
from eth_utils import is_checksum_address


def get_address(msg: str) -> str:
    while True:
        val = input(msg)
        if is_checksum_address(val):
            return val
        else:
            addr = web3.ens.address(val)
            if addr:
                print(f"Found ENS '{val}' [{addr}]")
                return addr
        print(f"I'm sorry, but '{val}' is not a checksummed address or ENS")


def main():
    Vault = pm(config["dependencies"][0]).Vault
    print(f"You are using the '{network.show_active()}' network")
    dev = accounts.load(click.prompt("Account", type=click.Choice(accounts.load())))
    print(f"You are using: 'dev' [{dev.address}]")
    token = interface.ERC20(get_address("ERC20 Token: "))
    gov = get_address("Yearn Governance [ychad.eth]: ")
    rewards = get_address(
        "Rewards contract [0x93A62dA5a14C80f265DAbC077fCEE437B1a0Efde]: "
    )
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
    print("Deploying Vault...")
    vault = dev.deploy(Vault, token, gov, rewards, name, symbol)
