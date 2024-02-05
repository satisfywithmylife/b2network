# -*- coding: utf-8 -*-
# Time     :2024/1/22 00:36
# Author   :ym
# File     :bera_tools.py
import json
import random
import time
from typing import Union

import requests
from eth_account import Account
from eth_typing import Address, ChecksumAddress
from faker import Faker
from requests import Response
from web3 import Web3
from config import *

class B2Network():
    
    def __init__(self, pk: str, endpoint='https://ethereum-goerli.publicnode.com', b2_endpoint='', solver='', solver_key='', proxy={}, gas_scala=1.2) -> None:
        self.pk = pk.strip(),
        self.w3 = Web3(Web3.HTTPProvider(endpoint, request_kwargs={"proxies": {"http": proxy, "https": proxy}}))
        self.b2w3 = Web3(Web3.HTTPProvider(b2_endpoint, request_kwargs={"proxies": {"http": proxy, "https": proxy}}))
        self.solver = solver
        self.solver_key = solver_key
        self.proxy = proxy
        self.gas_scala = gas_scala
        self.explorer = ''
        self.b2_explorer = ''
        self.account = Account.from_key(pk)
        self.session = requests.session()
        # self.faucet_url = 'https://faucet.triangleplatform.com/ethereum/goerli'
        self.website_key = '6LcpMagiAAAAAFgz-g_wSopLeaW03zBrfYNGc34Q'
        
    def get_2captcha_google_token(self) -> Union[bool, str]:
        if self.solver_key == '':
            raise ValueError('2captcha_client_key is null ')
        params = {'key': self.solver_key, 'method': 'userrecaptcha', 'version': 'v3', 'action': 'submit',
                  'min_score': 0.5,
                  'googlekey': self.website_key,
                  'pageurl': self.faucet_url,
                  'json': 1}
        response = requests.get(f'https://2captcha.com/in.php?', params=params).json()
        if response['status'] != 1:
            raise ValueError(response)
        task_id = response['request']
        for _ in range(60):
            response = requests.get(
                f'https://2captcha.com/res.php?key={self.client_key}&action=get&id={task_id}&json=1').json()
            if response['status'] == 1:
                return response['request']
            else:
                time.sleep(3)
        return False

    def get_yescaptcha_google_token(self) -> Union[bool, str]:
        if self.solver_key == '':
            raise ValueError('yes_captcha_client_key is null ')
        json_data = {"clientKey": self.solver_key,
                     "task": {"websiteURL": self.faucet_url,
                              "websiteKey": self.website_key,
                              "type": "RecaptchaV3TaskProxylessM1S7", "pageAction": "submit"}, "softID": 109}
        response = self.session.post(url='https://api.yescaptcha.com/createTask', json=json_data).json()
        if response['errorId'] != 0:
            raise ValueError(response)
        task_id = response['taskId']
        time.sleep(5)
        for _ in range(30):
            data = {"clientKey": self.solver_key, "taskId": task_id}
            response = requests.post(url='https://api.yescaptcha.com/getTaskResult', json=data).json()
            if response['status'] == 'ready':
                return response['solution']['gRecaptchaResponse']
            else:
                time.sleep(2)
        return False

    def get_ez_captcha_google_token(self) -> Union[bool, str]:
        if self.solver_key == '':
            raise ValueError('ez-captcha is null ')
        json_data = {
            "clientKey": self.solver_key,
            "task": {"websiteURL": self.faucet_url,
                     "websiteKey": self.website_key,
                     "type": "ReCaptchaV3TaskProxyless", }, 'appId': '34119'}
        response = self.session.post(url='https://api.ez-captcha.com/createTask', json=json_data).json()
        if response['errorId'] != 0:
            raise ValueError(response)
        task_id = response['taskId']
        time.sleep(5)
        for _ in range(30):
            data = {"clientKey": self.solver_key, "taskId": task_id}
            response = requests.post(url='https://api.ez-captcha.com/getTaskResult', json=data).json()
            if response['status'] == 'ready':
                return response['solution']['gRecaptchaResponse']
            else:
                time.sleep(2)
        return False
    
    def _get_solver_provider(self):
        provider_dict = {
            'yescaptcha': self.get_yescaptcha_google_token,
            '2captcha': self.get_2captcha_google_token,
            'ez-captcha': self.get_ez_captcha_google_token,
        }
        if self.solver not in list(provider_dict.keys()):
            raise ValueError("solver_provider must be 'yescaptcha' or '2captcha' or 'ez-captcha' ")
        return provider_dict[self.solver]()
        
    def add_log(self, log_str, tx_hash):
        pass

    def faucet(self):
        payload = {
            'address': self.account.address,
            'network': 'ethereum_goerli',
            'token_v3': self._get_solver_provider()
        }
        if not payload['token_v3']:
            raise ValueError('获取google token 出错')
        
        headers = {
            'authority': 'artio-80085-ts-faucet-api-2.berachain.com',
            'accept': '*/*',
            'accept-language': 'zh-CN,zh;en-US;q=0.8,en;q=0.7,zh-TW;q=0.6,zh-HK;q=0.5',
            'cache-control': 'no-cache',
            'content-type': 'application/json;charset=UTF-8',
            'origin': 'https://faucet.triangleplatform.com', 
            'pragma': 'no-cache',
            'referer': 'https://faucet.triangleplatform.com/ethereum/goerli', 
            'user-agent': Faker().chrome(),
            "Fp": "2069e3823cc0683654979a026ba5376d",
            "Fp-Vid": "2069e3823cc0683654979a026ba5376d"
        }
    
        res = self.session.post(url='https://faucet.triangleplatform.com/api/request', json=payload, timeout=30, headers=headers, proxies=self.proxy)
        res = res.json()
        if res.get('txhash'):
            return True
        
        return False
    
    def swap_usdc(self):
        amount = random.uniform(0.00005, 0.0001)
        contract = self.w3.eth.contract(address=goerli_symbiosis_contract_address, abi=self.load_abi('swap'))
        txn = contract.functions.swapExactETHForTokens(
            0,
            [goerli_weth_address, goerli_usdc_address],
            self.account.address,
            int(time.time()+3600)
        )
        return self._make_tx(txn, Web3.to_wei(amount, 'ether'))
        #login#1707066395#0x91f0f8f18cdd2d091fc0a41f801729d22daf0be7

    def approve_token(self, spender: Union[Address, ChecksumAddress], amount: int,
                      approve_token_address: Union[Address, ChecksumAddress]) -> str:
        """
        授权代币
        :param spender: 授权给哪个地址
        :param amount: 授权金额
        :param approve_token_address: 需要授权的代币地址
        :return: hash
        """
        approve_contract = self.w3.eth.contract(address=approve_token_address, abi=self.load_abi('erc20'))
        allowance_balance = approve_contract.functions.allowance(self.account.address, spender).call()
        if allowance_balance > amount:
            return ''
        txn = approve_contract.functions.approve(spender, amount)
        return self._make_tx(txn)
    
    def meson_bridge_usdc_to_b2(self):
        
        usdc_amount = random.randint(150, 450)
        # 授权usdc
        self.approve_token(goerli_meson_contract_address, usdc_amount, goerli_usdc_address)
        txn = self.w3.eth.contract(address=goerli_meson_contract_address, abi=self.load_abi("meson")).directExecuteSwap(
            encodedSwap='',
            r='',
            yParityAndS='',
            initiator=self.account.address,
            recipient=self.account.address
        )
        
        return self._make_tx(txn)
    
    def _get_bridge_swap_params(self):
        sign_message = ''
        
    
    def b2_glow_swap(self):
        pass
    
    def b2_glow_add_lp(self):
        pass
    
    def b2_glow_stack(self):
        pass
    
    def claim_point(self):
        pass
    
    def _make_tx(self, txn, eth_amount=0):
        tx = txn.build_transaction({
            'gas': 0, 
            'value': int(eth_amount),
            'gasPrice': int(self.w3.eth.gas_price * self.gas_scala),
            'nonce': self.w3.eth.get_transaction_count(self.account.address)
        })
        tx.update({
            'gas': self.w3.eth.estimate_gas(tx)+ random.randint(10000, 50000)
        })
        signed_txn = self.account.sign_transaction(tx)
        order_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        try:
            self.w3.eth.wait_for_transaction_receipt(order_hash)
        except Exception as e:
            if 'is not in the chain after 120 seconds' in f'{e}':
                pass
        return order_hash.hex()
    
    def load_abi(self, abi_name):
        with open(f'./abi/{abi_name}.json', 'r') as f:
            json_data = json.load(f)
            return json_data
    
    
if __name__ == '__main__':
    pk = ''
    b2 = B2Network(pk=pk)
    print(b2.swap_usdc())