"""Print the canonical protocol-v3 prospective power analysis as JSON."""

import json

from purposebench.v3.power import protocol_v3_power_report

if __name__ == "__main__":
    print(json.dumps(protocol_v3_power_report(), indent=2, sort_keys=True))
