"""Validate clinical-release safety labels on developer-only JSON reports."""


def validate(report):
    if not isinstance(report, dict):
        raise ValueError('report_object_required')
    # Reports may use the historical clinical_acceptance field, but must make
    # a non-clinical status explicit; omission is not treated as false.
    independent = report.get('independent_clinical_gold')
    release = report.get('real_patient_release_authorized')
    acceptance = report.get('clinical_acceptance')
    if independent is not False and acceptance is not False:
        raise ValueError('clinical_gold_flag_required')
    if release is not False and acceptance is not False:
        raise ValueError('clinical_release_flag_required')
    return {'safe': True, 'independent_clinical_gold': False,
            'real_patient_release_authorized': False}
