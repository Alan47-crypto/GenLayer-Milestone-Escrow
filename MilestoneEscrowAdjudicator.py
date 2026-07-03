# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from genlayer import *
from datetime import datetime, timezone
import json
from dataclasses import dataclass

@allow_storage
@dataclass
class Bounty:
    client: Address
    worker: Address
    amount: u256
    deadline: u32
    specification: str
    evidence_url: str
    status: str 
    quality_score: u8

class MilestoneEscrowAdjudicator(gl.Contract):
    bounties: TreeMap[u256, Bounty]
    bounty_count: u256

    def __init__(self):
        self.bounty_count = u256(0)

    @gl.public.write.payable
    def create_bounty(self, worker_hex: str, deadline_timestamp: u32, specification: str) -> u256:
        deposit_value = gl.message.value
        if deposit_value == u256(0):
            raise gl.vm.UserError("Bounty requires funded escrow deposit.")
        
        now = int(datetime.now(timezone.utc).timestamp())
        if deadline_timestamp <= now:
            raise gl.vm.UserError("Deadline must be in the future.")

        bounty_id = self.bounty_count
        
        self.bounties[bounty_id] = Bounty(
            client=gl.message.sender_address,
            worker=Address(worker_hex),
            amount=deposit_value,
            deadline=deadline_timestamp,
            specification=specification,
            evidence_url="",
            status="ACTIVE",
            quality_score=u8(0)
        )
        
        self.bounty_count = self.bounty_count + u256(1)
        return bounty_id

    @gl.public.write
    def submit_work(self, bounty_id: u256, evidence_url: str) -> None:
        bounty = self.bounties.get(bounty_id, None)
        if bounty is None:
            raise gl.vm.UserError("Bounty does not exist.")
        if gl.message.sender_address != bounty.worker:
            raise gl.vm.UserError("Only the assigned worker can submit deliverables.")
        if bounty.status != "ACTIVE":
            raise gl.vm.UserError("Bounty is not active.")

        bounty.evidence_url = evidence_url
        self.bounties[bounty_id] = bounty

    @gl.public.write
    def claim_expired_refund(self, bounty_id: u256) -> None:
        bounty = self.bounties.get(bounty_id, None)
        if bounty is None:
            raise gl.vm.UserError("Bounty does not exist.")
        if gl.message.sender_address != bounty.client:
            raise gl.vm.UserError("Only the client can claim an expired refund.")
        if bounty.status != "ACTIVE":
            raise gl.vm.UserError("Bounty is already resolved.")
        if bounty.evidence_url != "":
            raise gl.vm.UserError("Worker submitted evidence; must use adjudication path.")

        now = int(datetime.now(timezone.utc).timestamp())
        if now <= bounty.deadline:
            raise gl.vm.UserError("Deadline has not passed yet.")

        bounty.status = "REFUNDED"
        self.bounties[bounty_id] = bounty
        
        @gl.evm.contract_interface
        class _TransferGhost:
            class View: pass
            class Write: pass

        _TransferGhost(bounty.client).emit_transfer(value=bounty.amount)

    @gl.public.write
    def adjudicate_milestone(self, bounty_id: u256) -> None:
        bounty = self.bounties.get(bounty_id, None)
        if bounty is None:
            raise gl.vm.UserError("Bounty does not exist.")
        if bounty.status != "ACTIVE":
            raise gl.vm.UserError("Bounty is not open for adjudication.")
        if bounty.evidence_url == "":
            raise gl.vm.UserError("No work submitted yet.")

        mem_bounty = gl.storage.copy_to_memory(bounty)

        def leader_fn():
            response = gl.nondet.web.get(mem_bounty.evidence_url)
            if response.status != 200:
                raise gl.vm.UserError(f"[EXTERNAL] Evidence URL unreachable: {response.status}")
            
            deliverable_content = response.body.decode("utf-8")[:4000]
            
            prompt = f"""
            You are a neutral decentralized adjudicator reviewing an engineering bounty submission.
            
            Core Specification/Requirements:
            {mem_bounty.specification}
            
            Submitted Deliverable Material:
            {deliverable_content}
            
            Evaluate if the deliverable satisfies the core criteria specified. 
            Assign an integer quality score from 1 to 10. If key features are omitted or broken, score under 5.
            Determine if the resolution status should be "COMPLETED" (payout approved) or "DISPUTED" (needs changes/rejected).

            Your response must be perfectly parseable JSON matching this schema precisely:
            {{
                "reasoning": "Brief objective cross-reference of work against specifications",
                "quality_score": int,
                "resolution": "COMPLETED" or "DISPUTED"
            }}
            """
            return gl.nondet.exec_prompt(prompt, response_format="json")

        def validator_fn(leaders_res) -> bool:
            if not isinstance(leaders_res, gl.vm.Return):
                try:
                    leader_fn()
                    return False
                except gl.vm.UserError as e:
                    return str(e) == getattr(leaders_res, 'message', '')
                except Exception:
                    return False

            validator_data = leader_fn()
            leader_data = leaders_res.calldata

            verdict_matches = (leader_data.get("resolution") == validator_data.get("resolution"))
            
            score_diff = abs(int(leader_data.get("quality_score", 0)) - int(validator_data.get("quality_score", 0)))
            score_acceptable = (score_diff <= 1)

            if int(leader_data.get("quality_score", 0)) < 5 or int(validator_data.get("quality_score", 0)) < 5:
                return verdict_matches and (leader_data.get("resolution") == "DISPUTED")

            return verdict_matches and score_acceptable

        adjudication_verdict = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

        bounty.status = adjudication_verdict["resolution"]
        bounty.quality_score = u8(adjudication_verdict["quality_score"])
        self.bounties[bounty_id] = bounty

        @gl.evm.contract_interface
        class _PayoutGhost:
            class View: pass
            class Write: pass

        if bounty.status == "COMPLETED":
            _PayoutGhost(bounty.worker).emit_transfer(value=bounty.amount)

    @gl.public.view
    def get_bounty_status(self, bounty_id: u256) -> str:
        bounty = self.bounties.get(bounty_id, None)
        if bounty is None:
            return "Bounty not found"
        return f"Status: {bounty.status}, Quality Score: {bounty.quality_score}/10"