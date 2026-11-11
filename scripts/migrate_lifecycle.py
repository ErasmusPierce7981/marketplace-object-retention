import json

from marketplace_retention.infrai import InfraiClient
from marketplace_retention.migration import migrate_from_s3_lifecycle
from marketplace_retention.models import MigrationRequest


def main() -> None:
    request = MigrationRequest(
        bucket="marketplace-throwaway-media",
        sweep_url=(
            "https://marketplace.example.com/internal/object-sweep/"
            "marketplace-throwaway-media"
        ),
    )
    result = migrate_from_s3_lifecycle(request, InfraiClient())
    print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    main()
