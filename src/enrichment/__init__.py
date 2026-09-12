"""Claim-based enrichment framework: providers propose, resolution disposes.

Takes any list of organization names and iterates it through public sources —
SEC EDGAR first, then FRED macro context, registries, geography and the open
web — to produce an auditable customer/vendor master.

The one rule that makes it work: a provider never writes to a record. It emits
:class:`~enrichment.core.model.Claim` objects carrying a value, a confidence and
the evidence behind it. Resolution happens later, once, in
:mod:`enrichment.core.golden`. That is what keeps "why does it say that?" a
question with an answer instead of a bug found in a board meeting.

Models live in ``warehouse`` (see ``EnrichmentDataset`` and friends); this app
holds only logic, the same way ``sec_edgar`` does.
"""
