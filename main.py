# -*- coding: utf-8 -*-
import json
import sys
import random
import time
from typing import Union

import requests
from eth_account import Account
from eth_typing import Address, ChecksumAddress
from faker import Faker
# from requests import Response
from web3 import Web3
from config import *
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_abi import encode
from loguru import logger
from functools import cached_property
from hashlib import sha256



logger.remove()
logger.add('my.log', format='<g>{time:YYYY-MM-DD HH:mm:ss:SSS}</g> | <c>{level}</c> | <level>{message}</level>')
logger.add(sys.stdout, format='<g>{time:YYYY-MM-DD HH:mm:ss:SSS}</g> | <c>{level}</c> | <level>{message}</level>')

class B2Network():
    
    def __init__(self, pk: str, b2_endpoint='https://habitat-rpc.bsquared.network/', proxy='', gas_scala=1, invite_code='') -> None:
        self.pk = pk
        self.b2w3 = Web3(Web3.HTTPProvider(b2_endpoint, request_kwargs={"proxies": {"http": proxy, "https": proxy}}))
        self.spw3 = Web3(Web3.HTTPProvider('https://gateway.tenderly.co/public/sepolia', request_kwargs={"proxies": {"http": proxy, "https": proxy}}))
        self.proxy = {'http:': proxy, 'https': proxy}
        self.gas_scala = gas_scala
        self.b2_explorer = 'https://habitat-explorer.bsquared.network/tx/{}'
        self.account = Account.from_key(pk)
        self.session = requests.session()
        self.b2_login_str = 'login#{}#{}'
        self.access_token = ''
        self.invite_code = invite_code
        
        
    def add_log(self, log_str, tx_hash=''):
        log_str = f'{self.account.address[:32]}******************** ' + log_str
        
        if tx_hash and isinstance(tx_hash, str):
            log_str += f' | {self.b2_explorer.format(tx_hash)}'
        logger.debug(log_str)
    
    def b2_faucet(self):
        url = f'https://task-openapi.bsquared.network/v1/faucet?is_aa=false&to_address={self.account.address}'
        res = requests.get(url=url, proxies=self.proxy, timeout=30).json()
        if res['code'] == "0":
            self.add_log(f'领水成功, {json.dumps(res)}')
            return True
        raise Exception(f'b2领水错误，原因: {res["message"]}')
   
    def approve_token(self, spender: Union[Address, ChecksumAddress], amount: int, approve_token_address: Union[Address, ChecksumAddress], gas=0) -> str:
        """
        授权代币
        :param spender: 授权给哪个地址
        :param amount: 授权金额
        :param approve_token_address: 需要授权的代币地址
        :return: hash
        """
        
        approve_contract = self.b2w3.eth.contract(address=approve_token_address, abi=self.load_abi('erc20'))
        allowance_balance = approve_contract.functions.allowance(self.account.address, spender).call()
        if allowance_balance > amount: # 如果已授权额度已经大于当前要授权额度，则跳过授权
            return ''
        txn = approve_contract.functions.approve(spender, amount)
        return self._make_tx(txn=txn, gas=gas)
    
    def b2_login(self):
        ts = int(time.time())
        if self.access_token:
            return self.access_token
        text=self.b2_login_str.format(ts, self.account.address.lower())
        msghash = encode_defunct(text=text)
        sign = Account.sign_message(msghash, self.pk)
       
        url = 'https://task-api.bsquared.network/v2/user/access-token'
        payload = {
            'timestamp': ts,
            'signer': self.account.address,
            'signature': str(sign.signature.hex()).replace('0x', '0x00')+self.account.address[2:]
        }
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json;charset=UTF-8',
            'Origin': 'https://task.bsquared.network',
            'Referer': 'https://task.bsquared.network',
            'User-Agent': Faker().chrome()
        }
        res = self.session.post(url=url, json=payload, timeout=30, proxies=self.proxy, headers=headers)
        
        res = res.json()
        if res['code']:
            raise Exception(f'登录b2失败，错误原因：{res["msg"]}')
        
        self.access_token = res['data']['access_token']
        self.add_log(f'登陆成功， access_token: {self.access_token}')
        return self.access_token
    
    def b2_glow_swap(self, coin, amount=0.000015):
        swap_amount = Web3.to_wei(amount, 'ether')
        contract = self.b2w3.eth.contract(address=b2_testnet_blow_contract_address, abi=self.load_abi('blow'))
        if coin == 'usdc':
            swap_path = (b2_testnet_wbtc_address+b2_testnet_usdc_address).replace('0x', '0009c4')[6:]
        else:
            swap_path = (b2_testnet_wbtc_address+b2_testnet_usdt_address).replace('0x', '000064')[6:]
        args = [[
            Web3.to_bytes(hexstr=swap_path),
            self.account.address,
            int(time.time()+2*3600),
            swap_amount,
            0
        ]]
        txn = contract.encodeABI(fn_name='exactInput', args=args)
        tx_hash = self._make_tx(txn, swap_amount, True, b2_testnet_blow_contract_address)
        self.add_log(f'b2swap 兑换 {coin} 成功', tx_hash)
    
    def b2_glow_add_lp(self, usdc_amount=300):
        usdt_amount = 0
        usdc_amount = int(usdc_amount*1e6)

        self.approve_token(b2_testnet_blow_lp_contract_address, usdc_amount, b2_testnet_usdc_address, 170000)
        contract = self.b2w3.eth.contract(address=b2_testnet_blow_lp_contract_address, abi=self.load_abi('position'))
      
        fee = 100
        usdt_amount_min = int(usdt_amount*(1-0.001))
        usdc_amount_min = int(usdc_amount*(1-0.001))
        txn = contract.encodeABI(fn_name='mint', args=[(
            b2_testnet_usdt_address,
            b2_testnet_usdc_address,
            fee,
            379,
            419,
            usdt_amount,
            usdc_amount,
            usdt_amount_min,
            usdc_amount_min,
            self.account.address,
            int(time.time()+1800)
        )])

        tx_hash = self._make_tx(txn=txn, is_data=True, spender=b2_testnet_blow_lp_contract_address)
        self.add_log('添加流动性成功！', tx_hash)
        
    def b2_glow_stack(self):
        contract = self.b2w3.eth.contract(address=b2_testnet_blow_lp_contract_address, abi=self.load_abi('position'))
        lp_nft_num = contract.functions.balanceOf(self.account.address).call()
        if not lp_nft_num:
            self.add_log('未发现流动性')
            return

        for i in range(lp_nft_num):
            token_id = contract.functions.tokenOfOwnerByIndex(self.account.address, i).call()
            if not token_id:
                continue
            data = '0xfc6f7865'+encode(['uint256', 'address', 'uint256', 'uint256'], [
                int(token_id),
                self.account.address,
                340282366920938463463374607431768211455, # 0xffff....
                340282366920938463463374607431768211455 # 0xffff....
            ]).hex()
            hex_data = self.b2w3.eth.call({'to': b2_testnet_blow_lp_contract_address, 'data': data, 'from': self.account.address}).hex()
            data_list = self.b2w3.codec.decode(["uint256", "uint256"], bytes.fromhex(hex_data[2:]))
            if data_list[1]:
                continue        
           
            txn = contract.functions.safeTransferFrom(self.account.address, b2_stable_coin_lp_contract_address, token_id)
            tx_hash = self._make_tx(txn=txn, gas=250000)
            self.add_log('stack 成功', tx_hash, True)

        
    def invite(self):
        u_info = self.get_user_info()
        if u_info['inviter'] or not self.invite_code:
            self.add_log('已经存在邀请人或邀请码为空，跳过')
            return
        url='https://task-api.bsquared.network/v2/user/inviter'
        payload = {
            'code': self.invite_code
        }
        res = requests.post(url=url, json=payload, proxies=self.proxy, timeout=30, headers=self.get_auth_header()).json()
        if res['code']:
            raise Exception(f'用户填写邀请码{self.invite_code}失败, 原因：{res["msg"]}')
        
        return self.add_log(f'被邀请成功，邀请人邀请码：{self.invite_code}')
        
    def contract_faucet(self, coin_type):
        contract_map = {
            'usdc': b2_testnet_usdc_address,
            'eth': b2_testnet_eth_address,
            'usdt': b2_testnet_usdt_address
        }
        if not contract_map.get(coin_type):
            raise Exception('水龙头只支持，usdc,eth,usdt 这三种测试代币类型')
        contract = self.b2w3.eth.contract(address=contract_map[coin_type], abi=self.load_abi('erc20'))
        txn = contract.functions.faucet(self.account.address)
        tx_hash = self._make_tx(txn=txn, gas=350000)
        self.add_log(f'领取测试代币{coin_type}成功！', tx_hash)
        
    def get_user_info(self):
        url='https://task-api.bsquared.network/v2/user/profile'
        res = requests.get(url=url, proxies=self.proxy, timeout=30, headers=self.get_auth_header()).json()
        if res['code']:
            raise Exception(f'用户信息获取失败, 原因：{res["msg"]}')
        self.add_log(f'用户信息获取成功, {json.dumps(res)}')
        # {
        #     "code": 0,
        #     "msg": "success",
        #     "data": {
        #         "user_id": "3d8a6xxxxxxxxxxe6bf0xxxb",
        #         "twitter": "",
        #         "code": "aass",
        #         "inviter": "",
        #         "medals": 0,
        #         "referrals": 0,
        #         "register_timestamp": 17077656413,
        #         "points": 67,
        #         "medals_rank": 1,
        #         "referrals_rank": 0,
        #         "points_rank": 5056,
        #         "addresses": [
        #             {
        #                 "address": "0x91FhghfhjhxkC0a41f801729D22daFffff",
        #                 "sca_address": "0xd25jfjv81A57eb9vn5424B43yyyhdfhc",
        #                 "network": 0,
        #                 "address_type": 0
        #             }
        #         ]
        #     }
        # }
        return res['data']
        

        
    def claim_point(self):
        task_tpyes = {
            # glowswap 任务
            'https://task-glowswap.bsquared.network/task/refresh': [
                "glowswap_deposit",
                "glowswap_swap",
                "glowswap_add_liquidity"
            ],
            # 社交账号任务
            # 'https://task-media.bsquared.network/task/refresh': [
            #     "discord",
            #     "twitter",
            #     "telegram",
            # ],
            # 从btc测试网跨测试btc任务
            # 'https://task-bridge.bsquared.network/task/refresh': [
            #     "deposit",
            # ],
            # meson 来回跨稳定币任务
            # 'https://task-meson.bsquared.network/task/refresh': [
            #     "meson_gas_station",                
            #     "meson_withdraw",
            #     "meson_deposit",
            # ]
            # layerbank借贷任务
            'https://task-layerbank.bsquared.network/task/refresh': [
                'layerbank_supply',
                'layerbank_borrow',
            ],
            # owlto
            'https://task-meson.bsquared.network/task/refresh': [
                'owlto_deposit',
                'owlto_withdraw'
            ],
            # shoebill
            'https://task-meson.bsquared.network/task/refresh': [
                'shoebill_supply',
                'shoebill_borrow'
            ]
        }
        for task_url in task_tpyes.keys():
            for task_type in task_tpyes[task_url]:
                url = task_url + '?type=' + task_type
                headers = self.get_auth_header()
                res = requests.get(url=url, proxies=self.proxy, timeout=30, headers=headers).json()
                self.add_log(f'刷新任务 {task_type}, {json.dumps(res)}')
            
    def get_auth_header(self):
        access_token = self.b2_login()

        return  {
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'en-US;',
            'Authorization': 'Bearer ' + access_token,
            'Content-Type': 'application/json;charset=UTF-8',
            'Origin': 'https://task.bsquared.network',
            'Referer': 'https://task.bsquared.network/',
            'User-Agent': Faker().chrome()
        }
        
    def lend_supply(self, amount=0.0005):
        contract = self.b2w3.eth.contract(address=b2_lend_core, abi=self.load_abi('lend'))
        amount = Web3.to_wei(amount, 'ether')
        txn = contract.functions.supply(b2_lend_btc_market, amount)
        tx_hash = self._make_tx(txn=txn, eth_amount=amount, gas=150000)
        self.add_log('抵押btc成功', tx_hash)
    
    def lend_enter_market(self):
        contract = self.b2w3.eth.contract(address=b2_lend_core, abi=self.load_abi('lend'))
        txn = contract.functions.enterMarkets([b2_lend_btc_market])
        tx_hash = self._make_tx(txn=txn, gas=150000)
        self.add_log('打开btc抵押物开关成功', tx_hash)
        
    
    def lend_borrow(self, amount=0.01):
        contract = self.b2w3.eth.contract(address=b2_lend_core, abi=self.load_abi('lend'))
        amount = int(amount * 1e6)
        txn = contract.functions.borrow(b2_lend_borrow_usdc, amount)
        tx_hash = self._make_tx(txn=txn, gas=400000)
        self.add_log('借usdc成功', tx_hash)
        
    def get_shoebill_faucet(self, coin='weth'):
        coin_map = {
            'weth': shoebill_faucet_weth,
            'stone': shoebill_faucet_stone
        }
        coin_contract = coin_map.get(coin)
        if not coin_contract:
            self.add_log('coin 必须是 weth，stone 其中之一')
            return
        
        contract = self.b2w3.eth.contract(address=coin_contract, abi=self.load_abi('erc20'))
        tx = contract.functions.mint(self.account.address, Web3.to_wei(1, 'ether'))
        tx_hash = self._make_tx(txn=tx, gas=100000)
        self.add_log(f'获取 shoebill 水 {coin} 成功', tx_hash)
        
    def shoebill_supply(self, coin='weth'):
        coin_map = {
            'weth': shoebill_faucet_weth,
            'stone': shoebill_faucet_stone
        }
        coin_contract = coin_map.get(coin)
        if not coin_contract:
            self.add_log('抵押 coin 必须是 weth，stone 其中之一')
            return
        amount = Web3.to_wei(random.uniform(0.03, 0.09), 'ether')
        self.approve_token(shoebill_supply, Web3.to_wei(1, 'ether'), coin_contract, gas=100000)
        data = '0xa0712d68' + encode(['uint256'], [amount]).hex()
        tx_hash = self._make_tx(txn=data, is_data=1, spender=shoebill_supply, gas=1000000)
        self.add_log(f'shoebill 抵押 {coin} 成功', tx_hash)
        
    def shoebill_borrow(self, coin='stone'):
        coin_map = {
            'weth': shoebill_faucet_weth,
            'stone': shoebill_faucet_stone
        }
        coin_contract = coin_map.get(coin)
        if not coin_contract:
            self.add_log('借出 coin 必须是 weth，stone 其中之一')
            return
        amount = Web3.to_wei(random.uniform(0.001, 0.0015), 'ether')
        data = '0xc5ebeaec' + encode(['uint256'], [amount]).hex()
        tx_hash = self._make_tx(txn=data, is_data=1, spender=shoebill_borrow, gas=1000000)
        self.add_log(f'shoebill 借出 {coin} 成功', tx_hash)
        
    
    def _make_tx(self, txn, eth_amount=0, is_data=False, spender=None, gas=0, gas_price=0, use_sepolia=False):
        if use_sepolia:
            self.b2w3 = self.spw3
        if is_data:
            tx = {
                'chainId': self.b2w3.eth.chain_id,
                'value': int(eth_amount),
                'gas': 0, 
                'nonce': self.b2w3.eth.get_transaction_count(self.account.address),
                'gasPrice': gas_price if gas_price else int(self.b2w3.eth.gas_price * self.gas_scala),
                'data': txn,
                'to': spender,
                'from': self.account.address
            }
        else:
            tx = txn.build_transaction({
                'gas': 0, 
                'value': int(eth_amount),
                'gasPrice': gas_price if gas_price else int(self.b2w3.eth.gas_price * self.gas_scala),
                'nonce': self.b2w3.eth.get_transaction_count(self.account.address)
            })
        # print(tx)

        tx.update({
            'gas': gas if gas else self.b2w3.eth.estimate_gas(tx)
        })
        signed_txn = self.account.sign_transaction(tx)
        order_hash = self.b2w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        try:
            self.b2w3.eth.wait_for_transaction_receipt(order_hash)
        except Exception as e:
            if 'is not in the chain after 120 seconds' in f'{e}':
                pass
        return order_hash.hex()
    
    def owlto_bridge_to_sepolia(self):
        amount = Web3.to_wei(random.uniform(0.01, 0.016), 'ether')
        weth_contract = self.b2w3.eth.contract(address=b2_testnet_eth_address, abi=self.load_abi('erc20'))
        # w_amount = weth_contract.functions.balanceOf(self.account.address).call()
        # exit()
        tx = weth_contract.functions.transfer(owlto_sepolia_bridge, amount)
        tx_hash = self._make_tx(txn=tx, gas=50000)
        self.add_log(f'跨链 eth 到 sepolia', tx_hash)
        if self.post_owlto_request(tx_hash, amount, 5008):
            self.add_log('b2跨链成功')
        
    def post_owlto_request(self, tx_hash, amount, ext):
        payload = {
            'address': self.account.address,
            'chainid': self.b2w3.eth.chain_id,
            'nonce': self.b2w3.eth.get_transaction_count(self.account.address) -1,
            'tx_hash': tx_hash,
            'agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'sign': str(self.account.address) + 'owlto',
            'input_amount': int(amount - Web3.to_wei('0.005', 'ether')),
            'transation_amount': int(amount + ext),
            'wallet': 'MetaMask'
        }
        print(payload)
        res = requests.post(url='https://owlto.finance/api/config/tx-action', json=payload).json()
        if res['code'] >0:
            self.add_log(f'请求owlto失败，原因：{res["msg"]}')
            return False
        
        return True
    
    
    def owlto_bridge_from_sepolia(self):
        # 使用sepolia节点作为provider
        self.b2w3 = self.spw3
        if not self.b2w3.eth.get_balance(self.account.address):
            self.add_log('sepolia eth 余额不足')
            return False
        amount = Web3.to_wei(random.uniform(0.01, 0.016), 'ether')
        data = Web3.to_bytes(hexstr='0x')
        tx_hash = self._make_tx(txn=data, eth_amount=amount, is_data=1, spender=owlto_sepolia_bridge)
        self.add_log('跨 eth 到 b2 成功', tx_hash)
        if self.post_owlto_request(tx_hash, amount, 5033):
            self.add_log('sepolia跨链成功')
  
    
    def demail_mint(self, username):
        mint_nft_abi = [{
            "inputs": [
                {
                    "internalType": "address",
                    "name": "nft_owner",
                    "type": "address"
                },
                {
                    "internalType": "string",
                    "name": "nft_name",
                    "type": "string"
                }
            ],
            "name": "MintNFT",
            "outputs": [

            ],
            "stateMutability": "payable",
            "type": "function"
        }]
       
        contract = self.b2w3.eth.contract(address=Web3.to_checksum_address(dmain_nft),
                                     abi=mint_nft_abi)
        txn = contract.encodeABI(fn_name='MintNFT', args=(
            Web3.to_checksum_address(self.account.address),
            username
        ))

        tx_hash = self._make_tx(txn=txn, is_data=True, spender=dmain_nft)
        self.add_log('mint dmail nft 成功', tx_hash)

    def send_mail(self, username):
        send_mail_abi = [{
            "inputs": [
                {
                    "internalType": "string",
                    "name": "to",
                    "type": "string"
                },
                {
                    "internalType": "string",
                    "name": "path",
                    "type": "string"
                }
            ],
            "name": "send_mail",
            "outputs": [

            ],
            "stateMutability": "payable",
            "type": "function"
        }]
       
        path = self.account.address.lower() + '@dmail.ai'
        sha256_hash = sha256()
        sha256_hash.update(path.encode('utf-8'))
        # 获取哈希值的十六进制表示
        path = sha256_hash.hexdigest()

        sha256_hash.update(str(username + '@dmail.ai').encode('utf-8'))
        to = sha256_hash.hexdigest()
        contract = self.b2w3.eth.contract(address=Web3.to_checksum_address(dmain_send),
                                     abi=send_mail_abi)
        txn = contract.encodeABI(fn_name='send_mail', args=(
            to,
            path
        ))

        tx_hash = self._make_tx(txn=txn, is_data=True, spender=dmain_send)
        self.add_log('发送 dmail 邮件 成功', tx_hash)
        
    # 获取地板价
    def layercraft_market_floor_item(self):
        url = 'https://prod-api.layercraft.co/subgraphs/name/b2-nft-market-pre'
        payload = {
            'query': 'query ($pid: String!, $nid: String!, $orderBy: String!, $orderDirection: String!, $skip: Int = 0, $first: Int = 10, $keywords: String) {\n  nfts(\n    orderBy: $orderBy\n    orderDirection: $orderDirection\n    skip: $skip\n    first: $first\n    where: {isTradable: true, project: $pid, collection: $nid}\n  ) {\n    id\n    tokenId\n    nftType\n    count\n    otherId\n    metadataUrl\n    currentAskPrice\n    currentSeller\n    updatedAt\n    collection {\n      name\n      id\n      nftType\n    }\n  }\n  totalCount: nfts(where: {isTradable: true, project: $pid, collection: $nid}) {\n    id\n  }\n}',
            'variables': {
                'first': 8,
                'nid': layercraft_nft_contract_address,
                'orderBy': 'currentAskPrice',
                'orderDirection': 'asc',
                'pid': "1",
                'skip': 0
            }
        }
        
        res = requests.post(url=url, json=payload)
        res = res.json()
        return res['data']['nfts'][0]
    
    # 我的nft
    def layercraft_my_nft(self):
        url = f'https://habitat-backend.bsquared.network/api/v2/addresses/{self.account.address}/nft/collections?type='
        res = requests.post(url=url)
        res = res.json()
        if not res.get('items'):
            self.add_log('没有发现账户存在nft')
            return
        
        nfts = res['items'][0]['token_instances']
        nft_ids = [item['id'] for item in nfts]
        
        url = 'https://prod-api.layercraft.co/subgraphs/name/b2-nft-market-pre'
        payload = {
            'query': "query ($tokenIds: [String], $nft: String, $owner: String) {\n  unlistedNFTs: nfts(\n    where: {tokenId_in: $tokenIds, collection: $nft, isTradable: false}\n    orderBy: updatedAt\n    orderDirection: desc\n  ) {\n    id\n    tokenId\n    metadataUrl\n    nftType\n    otherId\n    currentAskPrice\n    updatedAt\n    isTradable\n    collection {\n      name\n      description\n      id\n    }\n  }\n  listedNFTs: nfts(\n    where: {currentSeller: $owner, isTradable: true}\n    orderBy: updatedAt\n    orderDirection: desc\n  ) {\n    id\n    tokenId\n    metadataUrl\n    nftType\n    otherId\n    currentAskPrice\n    updatedAt\n    isTradable\n    collection {\n      name\n      description\n      id\n    }\n  }\n  listed1155NFTs: nft1155Orders(\n    where: {seller: $owner, count_gt: \"0\", status: \"selling\", collection_: {active: true}}\n  ) {\n    nft {\n      id\n      tokenId\n      metadataUrl\n      nftType\n      otherId\n      currentAskPrice\n      updatedAt\n      isTradable\n      collection {\n        name\n        description\n        id\n      }\n    }\n  }\n}",
            'variables': {
                'nft': layercraft_nft_contract_address,
                'owner': self.account.address,
                'tokenIds': nft_ids
            }
        }
        res = requests.post(url=url, json=payload)
        res = res.json()
        unlist_id = res['data']['unlistedNFTs'][0]['tokenId']
        return unlist_id
    
    # 购买
    def layercraft_buy(self):
        floor_item = self.layercraft_market_floor_item()
        price = floor_item['currentAskPrice']
        id = floor_item['tokenId']
        
        if self.b2w3.eth.get_balance(self.account.address) < Web3.to_wei(price, 'ether'):
            self.add_log(f'余额不足，当前地板价为: {price} btc')
            return False

        
        tx = '0x0262d0c3' + encode(['address', 'uint256'], [layercraft_nft_contract_address, id]).hex()
        tx_hash = self._make_tx(txn=tx, is_data=True, spender=layercraft_market, eth_amount=Web3.to_wei(price))
        self.add_log('购买nft成功', tx_hash)
    
    # 上架
    def layercraft_sale(self):
        unlist_nftid = self.layercraft_my_nft()
        if not unlist_nftid:
            self.add_log('账户不存在未上架的nft')
            return
        # 授权
        self.nft_approve(layercraft_nft_contract_address, layercraft_market, unlist_nftid)
        
        floor_item = self.layercraft_market_floor_item()
        price = floor_item['currentAskPrice'] - 0.0001 # 取地板价-0.0001 作为售价

        list_tx = '0xdcbb63e6' + encode(['address','uint256','address','uint256'], [
            layercraft_nft_contract_address, # nft 
            unlist_nftid,
            layercraft_wbtc_address, # wbtc
            Web3.to_wei(price, 'ether')
        ]).hex()
        
        tx_hash = self._make_tx(txn=list_tx, is_data=True, spender=layercraft_market)
        self.add_log('上架nft成功', tx_hash)
        
    def nft_approve(self, nft_address, spender, nft_id):
        nft_contact = self.b2w3.eth.contract(address=nft_address, abi=self.load_abi('erc721'))
        approve_tx = nft_contact.functions.approve(spender, nft_id)
        tx_hash = self._make_tx(approve_tx)
        self.add_log('nft 授权成功', tx_hash)
        
    def load_abi(self, abi_name):
        with open(f'./abi/{abi_name}.json', 'r') as f:
            json_data = json.load(f)
            return json_data
    
    @staticmethod
    def write_file(file_name, log_str):
        with open(file=file_name, mode='a+') as f:
            f.write(f'{log_str}\n')
            
    @staticmethod    
    def iter_file(file_name):
        with open(file=file_name, encoding='utf-8') as f:
            for line in f.readlines():
                yield line.strip()

if __name__ == '__main__':
    pass

