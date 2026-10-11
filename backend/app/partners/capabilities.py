"""Exclusive closed partner catalog; never tenant role capabilities."""

PARTNER_CAPABILITIES = frozenset(
    {
        "partner.processes.read",
        "partner.timeline.read",
        "partner.logistics.update",
        "partner.processes.closure_report",
        "partner.documents.create",
        "partner.documents.read",
        "partner.payment_requests.create",
        "partner.payment_requests.read_org",
        "partner.payment_requests.submit",
        "partner.payment_requests.withdraw",
    }
)
