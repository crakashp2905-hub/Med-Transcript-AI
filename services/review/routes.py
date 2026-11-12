"""Review composition root; implementation lives in bounded routers/services."""

from services.review.service import ReviewService


def register_review_routes(
    app, database, identity, encounter, audit, require_processing, assets, profiles
):
    from services.review.providers import configured_provider
    from services.review.metrics_routes import register as register_metrics
    from services.review.clinical_routes import register as register_clinical
    from services.review.routers import (
        workspace,
        proposals,
        transcripts,
        notes,
        verification,
        approvals,
        amendments,
        exports,
        history,
    )

    app.state.drafting_provider = configured_provider()
    services = ReviewService(
        database, identity, encounter, audit, require_processing, assets, profiles
    )
    register_metrics(
        app, database, identity, encounter, require_processing, services.document, audit
    )
    register_clinical(
        app,
        database,
        identity,
        encounter,
        require_processing,
        services.get_tx,
        services.document,
        audit,
        profiles,
    )
    for router in (
        workspace,
        proposals,
        transcripts,
        notes,
        verification,
        approvals,
        amendments,
        exports,
        history,
    ):
        router.register(app, services)
