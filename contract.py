import smartpy as sp

# This class is only used in tests to emulate the HEN minter contract
# TODO stub out swap, collect, cancel_swap
class HENStubTester(sp.Contract):
    def __init__(self):
        self.init()
    
    @sp.entry_point
    def simulate_purchase(self, amount, dest):
        sp.send(dest, amount)

class HENDao(sp.Contract):
    def __init__(self, initOwners):
        # Owners are locked at initialization in this iteration
        # Future iterations could have dynamic owners
        self.init(
            owners=sp.set(initOwners),
            numOwners=sp.len(initOwners),
            locked=False,
            closed=False,
            lock_votes=sp.set([], sp.TAddress),
            close_votes=sp.set([], sp.TAddress),
            total_contributed=sp.mutez(0),
            total_liquidated=sp.mutez(0),
            liquidated_ledger=sp.big_map({}, sp.TAddress, sp.TMutez),
            equity=sp.big_map({}, sp.TAddress, sp.TMutez),
            buy_proposals=sp.big_map({}, sp.TNat, sp.TRecord(votes=sp.TSet(sp.TAddress), passed=sp.TBool)),
            swap_proposals=sp.big_map({}),
            cancel_swap_proposals=sp.big_map({}, sp.TNat, sp.TRecord(votes=sp.TSet(sp.TAddress), passed=sp.TBool)),
            swap_proposal_id=0,
            hen_address = sp.address("KT1Hkg5qeNhfwpKW4fXvq7HGZB9z2EnmCCA9")
        )

    # Vote to lock the contract
    # Once everyone votes, then self.data.locked = True, deposits are disabled
    # Pass in true to vote, false to undo vote.
    @sp.entry_point
    def vote_lock(self, vote):
        # If contract is already locked, then fail.
        sp.verify(
            ~self.data.locked &
            self.data.owners.contains(sp.sender)
        )
        
        sp.if vote:
            self.data.lock_votes.add(sp.sender)
        sp.else:
            self.data.lock_votes.remove(sp.sender)

        # If everyone voted, then set Locked to True,
        # record the state of equity, and reset vo
        sp.if sp.len(self.data.lock_votes) == self.data.numOwners:
            self.data.locked = True
    
    # Vote to close the contract
    # One closed, you can never use this contract for purchasing again
    # NFTs can still be sold, and people can withdraw.
    # This is so that equity in each NFT will remain constant.
    @sp.entry_point
    def vote_close(self, vote):
        sp.verify(
            ~self.data.closed & # Must not be closed
            self.data.locked & # And must be locked already
            self.data.owners.contains(sp.sender) # Must be owner
        )

        sp.if vote:
            self.data.close_votes.add(sp.sender)
        sp.else:
            self.data.close_votes.remove(sp.sender)

        # If everyone voted, then set closed to True,
        sp.if sp.len(self.data.close_votes) == self.data.numOwners:
            self.data.closed = True
    
    # Default entrypoint, this will be called when money is transferred to the account 
    @sp.entry_point
    def default(self):
        pass
    
    # Deposit money in the unlocked stage
    @sp.entry_point
    def deposit(self):
        sp.verify(
            self.data.owners.contains(sp.sender) &
            ~self.data.locked
        )

        # Initialize equity or add to existing
        sp.if self.data.equity.contains(sp.sender):
            self.data.equity[sp.sender] += sp.amount
        sp.else:
            self.data.equity[sp.sender] = sp.amount
        
        self.data.total_contributed += sp.amount
    
    # Withdraw money in the unlocked stage
    @sp.entry_point
    def withdraw(self, amount):
        sp.set_type(amount, sp.TMutez)
        
        # Verify that you are an owner and
        # that you only can withdraw as much as you contributed.
        sp.verify(
            self.data.owners.contains(sp.sender) &
            (self.data.equity[sp.sender] >= amount)
        )
        
        self.data.equity[sp.sender] -= amount
        self.data.total_contributed -= amount
        sp.send(sp.sender, amount)
    
    # Withdraw your money and then record that you have withdrew
    @sp.entry_point
    def liquidate(self):
        sp.verify(
            self.data.owners.contains(sp.sender) &
            self.data.closed # Must be closed before you can withdraw
        )
        
        # This should equal the sum of all money ever contributed to contract
        # Via either people or sales.
        real_total = sp.balance + self.data.total_liquidated

        # Calculate your split of the balance based on your equity
        
        amount_to_send = sp.local("amount_to_send", sp.mutez(0))
        amount_to_send.value = sp.split_tokens(
            self.data.equity[sp.sender],
            sp.utils.mutez_to_nat(real_total),
            sp.utils.mutez_to_nat(self.data.total_contributed)
        ) -  self.data.liquidated_ledger.get(sp.sender, sp.mutez(0))

        sp.verify(amount_to_send.value > sp.mutez(0))

        self.data.liquidated_ledger[sp.sender] = amount_to_send.value
        self.data.total_liquidated += amount_to_send.value

        # Send to caller
        sp.send(sp.sender, amount_to_send.value)
    
    # Vote for a specific "swap" on HEN
    # A swap is an objkt that is being sold at a specific price
    @sp.entry_point
    def vote_buy(self, swap_id, objkt_amount, price):
        sp.set_type(swap_id, sp.TNat)
        sp.set_type(objkt_amount, sp.TNat)
        sp.set_type(price, sp.TMutez)
        
        sp.verify(
            self.data.owners.contains(sp.sender) &
            self.data.locked &
            ~self.data.closed
        )

        sp.if self.data.buy_proposals.contains(swap_id):
            # If already passed, then fail
            sp.verify(~self.data.buy_proposals[swap_id].passed)
            
            self.data.buy_proposals[swap_id].votes.add(sp.sender)
        sp.else:
            votes = sp.set()
            votes.add(sp.sender)
            self.data.buy_proposals[swap_id] = sp.record(votes=votes, passed=False)

        # Everyone voted yes, execute the buy
        sp.if sp.len(self.data.buy_proposals[swap_id].votes) == sp.len(self.data.owners):
            self.hen_collect(swap_id, objkt_amount, price)
            self.data.buy_proposals[swap_id].passed = True

    # Undo a vote for a swap
    @sp.entry_point
    def undo_vote_buy(self, swap_id):
        sp.set_type(swap_id, sp.TNat)
        
        sp.verify(
            self.data.owners.contains(sp.sender) &
            self.data.locked &
            ~self.data.closed &
            ~self.data.buy_proposals[swap_id].passed
        )

        self.data.buy_proposals[swap_id].votes.remove(sp.sender)

    # Propose selling an objkt at a certain price point
    @sp.entry_point
    def propose_swap(self, objkt_amount, objkt_id, xtz_per_objkt):
        sp.set_type(objkt_amount, sp.TNat)
        sp.set_type(objkt_id, sp.TNat)
        sp.set_type(xtz_per_objkt, sp.TMutez)

        sp.verify(
            self.data.owners.contains(sp.sender) &
            self.data.locked
        )

        self.data.swap_proposals[self.data.swap_proposal_id] = sp.record(objkt_amount=objkt_amount, objkt_id=objkt_id, xtz_per_objkt=xtz_per_objkt, votes=sp.set([], sp.TAddress), passed=False)

        # Increment the proposal ID
        self.data.swap_proposal_id += 1
    
    # Vote for a proposal to sell an objkt
    # This will call HEN's swap() if everyone votes
    @sp.entry_point
    def vote_swap(self, swap_proposal_id):
        sp.set_type(swap_proposal_id, sp.TNat)
        
        sp.verify(
            self.data.owners.contains(sp.sender) &
            self.data.locked &
            self.data.swap_proposals.contains(swap_proposal_id) &
            ~self.data.swap_proposals[swap_proposal_id].passed
        )

        self.data.swap_proposals[swap_proposal_id].votes.add(sp.sender)
        
        sp.if sp.len(self.data.swap_proposals[swap_proposal_id].votes) == self.data.numOwners:
            self.hen_swap(swap_proposal_id)
            self.data.swap_proposals[swap_proposal_id].passed = True
    
    # Undo a vote for a proposal
    @sp.entry_point
    def undo_vote_swap(self, swap_proposal_id):
        sp.set_type(swap_proposal_id, sp.TNat)

        sp.verify(
            self.data.owners.contains(sp.sender) &
            self.data.locked &
            self.data.swap_proposals.contains(swap_proposal_id) &
            ~self.data.swap_proposals[swap_proposal_id].passed
        )

        self.data.swap_proposals[swap_proposal_id].votes.remove(sp.sender)

    # Vote to cancel an existing swap
    # This will call HEN's cancel() if everyone votes
    # swap_id - The swap to cancel, must be a valid swap_id that the contract owns
    @sp.entry_point
    def vote_cancel_swap(self, swap_id):
        sp.verify(
            self.data.owners.contains(sp.sender) &
            self.data.locked &
            self.data.cancel_swap_proposals.contains(swap_id) &
            ~self.data.cancel_swap_proposals[swap_id].passed
        )

        # Add to set of votes if it exists
        # Otherwise, create the set and initialize
        sp.if self.data.cancel_swap_proposals.contains(swap_id):
            self.data.cancel_swap_proposals[swap_id].votes.add(sp.sender)
        sp.else:
            self.data.cancel_swap_proposals[swap_id] = sp.record(votes=sp.set([sp.sender]), passed=False)

        sp.if sp.len(self.data.cancel_swap_proposals[swap_id].votes) == self.data.numOwners:
            self.hen_cancel_swap(swap_id)
    
    # Undo your vote to cancel an existing swap
    @sp.entry_point
    def undo_vote_cancel_swap(self, swap_id):
        sp.verify(
            self.data.owners.contains(sp.sender) &
            self.data.locked &
            self.data.cancel_swap_proposals.contains(swap_id) &
            ~self.data.cancel_swap_proposals[swap_id].passed
        )

        self.data.cancel_swap_proposals[swap_id].votes.remove(sp.sender)

    ### HEN Contract Functions ###    
    def hen_collect(self, swap_id, objkt_amount, price):
        c = sp.contract(sp.TPair(sp.TNat, sp.TNat), self.data.hen_address, entry_point = "collect").open_some()
        sp.transfer(sp.pair(objkt_amount, swap_id), price, c)

    def hen_swap(self, swap_proposal_id):
        # Check that the swap exists
        sp.if ~self.data.swap_proposals.contains(swap_proposal_id):
            sp.failwith("swap doesn't exist")

        # Get swap info
        swap_info = self.data.swap_proposals[swap_proposal_id]
        
        # Call into HEN contract
        c = sp.contract(sp.TPair(sp.TNat, sp.TPair(sp.TNat, sp.TMutez)), self.data.hen_address, entry_point = "swap").open_some()
        sp.transfer(sp.pair(swap_info.objkt_amount, sp.pair(swap_info.objkt_id, swap_info.xtz_per_objkt)), sp.mutez(0), c)

    def hen_cancel_swap(self, swap_id):
        c = sp.contract(sp.TNat, self.data.hen_address, entry_point = "cancel_swap").open_some()
        sp.transfer(swap_id, sp.mutez(0), c)

if "templates" not in __name__:
    @sp.add_test(name = "test_deposit_and_withdraw")
    def test():
        c1 = HENDao([sp.address("tz1owner1"), sp.address("tz1owner2")])
        stub = HENStubTester()
        stub.set_initial_balance(sp.mutez(10000))
        
        scenario = sp.test_scenario()
        scenario.h1("Test Deposits")
        scenario += c1
        scenario += stub
    
        user1 = sp.address("tz1owner1")
        user2 = sp.address("tz1owner2")
        hacker = sp.address("tz1hacker")

        c1.deposit().run(sender=user1, amount= sp.mutez(10))
        scenario.verify(c1.data.equity[user1] == sp.mutez(10))
        c1.deposit().run(sender=user1, amount= sp.mutez(5))
        scenario.verify(c1.data.equity[user1] == sp.mutez(15))
        scenario.verify(c1.data.total_contributed == sp.mutez(15))
        
        # Test withdraw
        c1.withdraw(sp.mutez(5)).run(sender=user1)
        scenario.verify(c1.data.equity[user1] == sp.mutez(10))
        scenario.verify(c1.data.total_contributed == sp.mutez(10))
        c1.deposit().run(sender=user1, amount= sp.mutez(5))

        
        # Hacker should not be able to deposit
        c1.deposit().run(valid=False, sender=hacker, amount=sp.mutez(10))
        
        # Second user deposits
        c1.deposit().run(sender=user2, amount=sp.mutez(45))
        scenario.verify(c1.data.equity[user2] == sp.mutez(45))
        scenario.verify(c1.data.total_contributed == sp.mutez(60))
        
        # Fund is locked
        c1.vote_lock(True).run(sender=user1)
        c1.vote_lock(True).run(sender=user2)
        
        # Deposits should be disabled
        c1.deposit().run(sender=user1, amount= sp.mutez(10), valid=False)
        c1.deposit().run(sender=user2, amount= sp.mutez(10), valid=False)
        
        # NFT is sold
        scenario.h1("NFT is sold")
        stub.simulate_purchase(dest=c1.address, amount=sp.mutez(100)).run(sender=user1)
        scenario.verify(c1.balance == sp.mutez(160))
        
        # Fund is closed
        c1.vote_close(True).run(sender=user1)
        c1.vote_close(True).run(sender=user2)
        
        # user1 has equity 15/60 = 25%
        # user2 has equity 45/60 = 75%;
        # Total balance after sale is 160
        # user1 owns 0.25 * 160 = 40
        # user2 owns 0.75 * 160 = 120

        # user1 withdraws
        c1.liquidate().run(sender=user1)
        scenario.verify(c1.balance == sp.mutez(120))

        # user2 withdraws
        c1.liquidate().run(sender=user2)
        scenario.verify(c1.balance == sp.mutez(0))
        
    
    @sp.add_test(name = "test_buy")
    def test():
        c1 = HENDao([sp.address("tz1owner1"), sp.address("tz1owner2")])
        scenario = sp.test_scenario()
        scenario.h1("Test Buy")
        scenario += c1
        user1 = sp.address("tz1owner1")
        user2 = sp.address("tz1owner2")

        scenario.h2("Buying disabled when locked")
        c1.vote_buy(swap_id=sp.nat(123), price=sp.mutez(0), objkt_amount=sp.nat(1)).run(valid=False, sender=user1)
        
        scenario.h2("Buying enabled when unlocked")
        c1.vote_lock(True).run(sender=user1)
        c1.vote_lock(True).run(sender=user2)
        
        c1.vote_buy(swap_id=sp.nat(123), objkt_amount=sp.nat(1), price=sp.mutez(0)).run(sender=user1)
        
        # Proposal should pass
        c1.vote_buy(swap_id=sp.nat(123), objkt_amount=sp.nat(1), price=sp.mutez(0)).run(sender=user2)
        scenario.verify(c1.data.buy_proposals[123].passed == True)
        
        # Double vote fails
        c1.vote_buy(swap_id=sp.nat(123), objkt_amount=sp.nat(1), price=sp.mutez(0)).run(sender=user2, valid=False)
        c1.vote_buy(swap_id=sp.nat(123), objkt_amount=sp.nat(1), price=sp.mutez(0)).run(sender=user1, valid=False)

        # Test undo
        c1.vote_buy(swap_id=sp.nat(456), objkt_amount=sp.nat(1), price=sp.mutez(5)).run(sender=user1)
        c1.undo_vote_buy(456).run(sender=user1)
        scenario.verify(c1.data.buy_proposals[456].votes.contains(user1) == False)


    @sp.add_test(name = "test_lock_and_close")
    def test():
        c1 = HENDao([sp.address("tz1owner1"), sp.address("tz1owner2")])
        scenario = sp.test_scenario()
        scenario.h1("Test Lock")
        scenario += c1
        user1 = sp.address("tz1owner1")
        user2 = sp.address("tz1owner2")
        
        scenario.h2("Contract starts unlocked")
        scenario.verify(c1.data.locked == False)

        scenario.h2("Users can call lock")
        c1.vote_lock(True).run(sender=user1)
        
        # Undo and redo lock
        c1.vote_lock(False).run(sender=user1)
        scenario.verify(~c1.data.lock_votes.contains(user1))
        c1.vote_lock(True).run(sender=user1)
        scenario.verify(c1.data.lock_votes.contains(user1))

        scenario.h2("Contract is unlocked when everyone locks")
        c1.vote_lock(True).run(sender=user2)
        scenario.verify(c1.data.locked == True)
        
        # Still should stay closed
        scenario.verify(c1.data.closed == False)
        
        # Vote for close
        c1.vote_close(True).run(sender=user1)
        
        # Undo and redo
        c1.vote_close(False).run(sender=user1)
        scenario.verify(~c1.data.close_votes.contains(user1))
        c1.vote_close(True).run(sender=user1)
        scenario.verify(c1.data.close_votes.contains(user1))
        
        # All users vote for close
        c1.vote_close(True).run(sender=user2)
        scenario.verify(c1.data.closed == True)
    
    @sp.add_test(name = "test_swap")
    def test():
        c1 = HENDao([sp.address("tz1owner1"), sp.address("tz1owner2")])
        scenario = sp.test_scenario()
        scenario.h1("Test Propose Swap")
        scenario += c1
        user1 = sp.address("tz1owner1")
        user2 = sp.address("tz1owner2")

        scenario.h2("Users can call propose swap")
        c1.vote_lock(True).run(sender=user1)
        c1.vote_lock(True).run(sender=user2)
        c1.propose_swap(objkt_amount=sp.nat(1), objkt_id=sp.nat(123), xtz_per_objkt=sp.mutez(10000)).run(sender=user1)
        c1.propose_swap(objkt_amount=sp.nat(1), objkt_id=sp.nat(456), xtz_per_objkt=sp.mutez(100)).run(sender=user2)
        scenario.verify(c1.data.swap_proposals[0].passed == False)
        scenario.verify(c1.data.swap_proposals[1].passed == False)
        
        # Undo votes
        c1.vote_swap(0).run(sender=user1)
        scenario.verify(c1.data.swap_proposals[0].votes.contains(user1))
        c1.undo_vote_swap(0).run(sender=user1)
        scenario.verify(~c1.data.swap_proposals[0].votes.contains(user1))
        
        
        scenario.h2("All votes for a swap")
        # Vote to pass the proposals
        c1.vote_swap(0).run(sender=user1)
        c1.vote_swap(0).run(sender=user2)
        
        c1.vote_swap(1).run(sender=user1)
        c1.vote_swap(1).run(sender=user2)
        
        # Test double vote fails
        c1.vote_swap(0).run(sender=user2, valid=False)

        # Verify that num votes is valid
        scenario.verify(sp.len(c1.data.swap_proposals[0].votes) == 2)
        
        # Verify that proposal is passed
        scenario.verify(c1.data.swap_proposals[0].passed == True)
        scenario.verify(c1.data.swap_proposals[1].passed == True)
        
        # Can't undo after passed
        c1.undo_vote_swap(0).run(sender=user1, valid=False)

    # TODO Add the initial addresses here when deploying contract
    sp.add_compilation_target("henDao", HENDao([]))
