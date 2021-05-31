import smartpy as sp

# buy_proposals swapId -> {[address]: boolean}
# Where swapId is a unique swap on HEN
# still needs a lot of work defining data structures etc.

class HENDao(sp.Contract):
    def __init__(self, initOwners):
        # Owners are locked at initialization in this iteration
        # Future iterations could have dynamic owners
        self.init(owners = sp.set(initOwners), numOwners=len(initOwners), locked=False, closed=False, lock_votes=sp.set(), close_votes=sp.set(), equity={}, total_contributed=sp.mutez(0), balance=sp.mutez(0), buy_proposals={}, swap_proposals={}, swap_votes={}, swap_proposal_id=0, did_withdraw=sp.set())
    
    # Vote to lock the contract
    # Once everyone votes, then self.data.locked = True, deposits are disabled
    @sp.entry_point
    def vote_lock(self):
        # If contract is already locked, then fail.
        sp.if self.data.locked:
            sp.failwith("already locked");

        sp.if self.data.owners.contains(sp.sender):
            self.data.lock_votes.add(sp.sender)
        
        # If everyone voted, then set Locked to True,
        # record the state of equity, and reset vo
        sp.if sp.len(self.data.lock_votes) == sp.len(self.data.owners):
            self.data.locked = True
    
    # Vote to close the contract
    # One closed, you can never use this contract for purchasing again
    # Unsold NFTs will be permanently locked into this contract
    @sp.entry_point
    def vote_close(self):
        sp.if ~self.data.locked:
            sp.failwith("can't close unless locked");

        sp.if self.data.owners.contains(sp.sender):
            self.data.close_votes.add(sp.sender)

        # If everyone voted, then set closed to True,
        sp.if sp.len(self.data.close_votes) == sp.len(self.data.owners):
            self.data.closed = True
            
            # Lock in the final balance, used for calculating withdrawals
            self.data.balance = sp.balance
    
    @sp.entry_point
    def deposit(self):
        sp.if ~self.data.owners.contains(sp.sender):
            sp.failwith("not owner");
        
        sp.if self.data.locked:
            sp.failwith("contract locked");
        
        # Initialize equity or add to existing
        sp.if self.data.equity.contains(sp.sender):
            self.data.equity[sp.sender] += sp.amount
        sp.else:
            self.data.equity[sp.sender] = sp.amount
        
        self.data.total_contributed += sp.amount
    
    # Withdraw your money and then record that you have withdrew
    @sp.entry_point
    def withdraw(self):
        sp.if ~self.data.closed:
            sp.failwith("not closed")
        
        sp.if ~self.data.owners.contains(sp.sender):
            sp.failwith("not owner")
        
        sp.if ~self.data.equity.contains(sp.sender):
            sp.failwith("no equity")

        sp.if self.data.did_withdraw.contains(sp.sender):
            sp.failwith("already withdrew")
        
        percent = self.data.equity[sp.sender] / self.data.total_contributed
        amount = percent * self.data.balance

        # Send to caller
        # sp.send(sp.sender, amount)
        # self.data.did_withdraw.add(sp.sender)
        
    
    # Vote for a specific "swap" on HEN
    # A swap is an objkt that is being sold at a specific price
    @sp.entry_point
    def vote_buy(self, params):
        sp.if ~self.data.owners.contains(sp.sender):
            sp.failwith("not owner")
        
        sp.if ~self.data.locked:
            sp.failwith("can't buy when unlocked")
        
        sp.if self.data.buy_proposals.contains(params.swap_id):
            self.data.buy_proposals[params.swap_id][sp.sender] = True
        sp.else:
            props = {}
            sp.set_type(props, sp.TMap(sp.TAddress, sp.TBool));
            props[sp.sender] = True
            self.data.buy_proposals[params.swap_id] = props
        
        # Everyone voted yes, execute the buy
        sp.if sp.len(self.data.buy_proposals[params.swap_id]) == sp.len(self.data.owners):
            self.buy_nft(params.swap_id)
    
    # Undo a vote for a swap
    @sp.entry_point
    def undo_vote_buy(self, params):
        sp.if ~self.data.owners.contains(sp.sender):
            sp.failwith("not an owner")
        
        sp.if ~self.data.locked:
            sp.failwith("fund locked")

        sp.if self.data.buy_proposals.contains(params.swap_id):
            del self.data.buy_proposals[params.swap_id][sp.sender]
    
    # Propose selling an objkt at a certain price point
    @sp.entry_point
    def propose_swap(self, params):
        
        self.data.swap_proposals[self.data.swap_proposal_id] = {
            objkt_amount: params.objkt_amount,
            objkt_id: params.objkt_id,
            xtz_per_objkt: params.xtz_per_objkt
        }
        
        votes = sp.set();
        votes.add(sp.sender);
        self.data.swap_votes[self.data.swap_proposal_id] = votes
        
        
        self.data.swap_proposal_id += 1
        pass
    
    # Vote for a proposal to sell an objkt
    # This will call HEN's swap() if everyone votes
    @sp.entry_point
    def vote_swap(self, params):
        self.data.swap_votes[params.swap_proposal_id].add(sp.sender)
        
        sp.if len(self.data.swap_votes[params.swap_id]) == self.data.numOwners:
            self.swap_nft(params.swap_proposal_id)
    
    # Undo a vote for a proposal
    @sp.entry_point
    def undo_vote_swap(self, params):
        self.data.swap_votes[params.swap_proposal_id].remove(sp.sender)

    # Vote to cancel an existing swap
    # This will call HEN's cancel() if everyone votes
    # params.swap_id - The swap to cancel, must be a valid swap_id that the contract owns
    @sp.entry_point
    def vote_cancel_swap(self, params):
        # Add to set of votes if it exists
        # Otherwise, create the set and initialize
        sp.if self.data.cancel_swap_votes.contains(params.swap_id):
            self.data.cancel_swap_votes[params.swap_id].add(sp.sender)
        sp.else:
            self.data.cancel_swap_votes[params.swap_id] = sp.set([sp.sender])
        
        sp.if len(self.data.cancel_swap_votes[params.swap_id]) == self.data.numOwners:
            self.cancel_swap(params.swap_id)
    
    # Undo your vote to cancel an existing swap
    @sp.entry_point
    def undo_vote_cancel_swap(self):
        self.data.cancel_swap_votes[params.swap_id].remove(sp.sender)
    
    ### HEN Contract Functions ###    
    def buy_nft(self, swap_id):
        hen_address = sp.address("KT1Hkg5qeNhfwpKW4fXvq7HGZB9z2EnmCCA9")
        c = sp.contract(sp.TPair(sp.TNat, sp.TNat), hen_address, entry_point = "collect").open_some()
        sp.transfer(sp.pair(1, swap_id), sp.mutez(0), c)

    def swap_nft(self, swap_proposal_id):
        pass
    
    def cancel_swap(self, swap_id):
        pass

if "templates" not in __name__:
    @sp.add_test(name = "Test_Deposit")
    def test():
        c1 = HENDao([sp.address("tz1owner1"), sp.address("tz1owner2")])
        scenario = sp.test_scenario()
        scenario.h1("Test Deposits")
        scenario += c1
        admin = sp.address("tz1owner1")
        user2 = sp.address("tz1owner2")
        hacker = sp.address("tz1hacker")
        c1.deposit().run(sender=admin, amount= sp.mutez(10))
        scenario.verify(c1.data.equity[admin] == sp.mutez(10))
        c1.deposit().run(sender=admin, amount= sp.mutez(5))
        scenario.verify(c1.data.equity[admin] == sp.mutez(15))
        c1.deposit().run(valid=False, sender=hacker, amount=sp.mutez(10))
    
    @sp.add_test(name = "Test_Buy")
    def test():
        c1 = HENDao([sp.address("tz1owner1"), sp.address("tz1owner2")])
        scenario = sp.test_scenario()
        scenario.h1("Test Buy")
        scenario += c1
        admin = sp.address("tz1owner1")
        user2 = sp.address("tz1owner2")

        scenario.h2("Buying disabled when locked")
        c1.vote_buy(swap_id=123).run(valid=False, sender=admin)
        
        scenario.h2("Buying enabled when unlocked")
        # TODO write this test

    # TODO Add the initial addresses here when deploying contract
    sp.add_compilation_target("henDao", HENDao([]))
