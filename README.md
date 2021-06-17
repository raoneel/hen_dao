# hen_dao
A DAO for shared ownershup of HEN NFTs


## Overview
* Enables a group of people to buy and sell HEN NFTs
* Profits are automatically split depending on how much money you contributed
* Proposals must be unanimously accepted in order to pass


## Locking
* Locked: A contract starts unlocked. In this phase, people can deposit money. The amount you deposit / total contributions is your equity.
* Users should call vote_lock() in order to vote to lock the contract
* Once locked, users can start buying and selling NFTs on HEN


## Buying/Selling
* vote_buy() takes a swap_id and a price. You need to provide the price because the contract doesn't know how much to send.
* You can use https://51rknuvw76.execute-api.us-east-1.amazonaws.com/dev/objkt?id=67545 to get the swap_id and price given an objkt ID
* propose_swap() is how you sell things, you will need an objkt ID, the amount you want to sell, and the price (in XTZ, 1,000,000 XTZ = 1 Tez)
* cancel_swap() is how you take things off the market


## Closing
* When you are done with the contract and want to withdraw money, you need to close it via vote_close()
* WARNING: Any unsold NFTs will be locked in the contract forever!
* Calling withdraw() will withdraw your share of the contract balance.
* Note, this system is needed because it is impossible to know which specific NFT was sold from the contract's perspective, so equity must be locked permanently.
