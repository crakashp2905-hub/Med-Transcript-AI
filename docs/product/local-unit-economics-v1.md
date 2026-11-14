# Local unit-economics estimate v1

The calculator reports per-encounter electricity and hardware amortization costs only when all required values are explicitly supplied with a `measured` or `assumed` basis. If any input is missing, both component costs and the total remain null. It does not infer a zero bill from absent telemetry.

The checked-in example uses clearly illustrative values: 45 W system draw, 120 s runtime, 5 demo currency units/kWh, 80% model availability, 800 demo currency units of hardware, 36 months amortization, 160 scheduled hours/month, and two encounters per available hour. Its result is scenario arithmetic, not a local electricity quote, device measurement, model benchmark, or investor forecast. The configured demo currency has no exchange-rate meaning.

Before a business case uses this estimate, replace the assumed wattage with metered system draw, runtime with a recorded model run, tariff with the deployment site's bill, availability with service logs, throughput with measured capacity, and capital/amortization values with sourced procurement assumptions. Keep clinician review labor separate until a qualified human timing study exists.
