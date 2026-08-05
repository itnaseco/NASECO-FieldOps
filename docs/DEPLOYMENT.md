# NASECO FieldOps Deployment Bundle

## What Is Bundled

Installing the app automatically imports the version-controlled FieldOps fixtures:

- FieldOps roles, role profiles, production-plan workflow and workflow actions.
- Crops, crop varieties, regions and visit types.
- QA inspection parameters, templates and Basic/Certified standards.
- Agronomy report templates, raw-data evaluation rules and activity templates.
- The standard maize crop recipe and its stage input requirements.
- The versioned 2026B pricing policies and production contract templates.

The Workspace, reports, pages, DocTypes, form scripts and controllers are standard app files and are
installed by Frappe schema synchronization rather than fixtures.

## What Is Deliberately Excluded

Fixtures do not contain Users, Companies, Accounts, Warehouses, Suppliers, Outgrowers, Farm Plots,
Crop Cycles, contracts, inspections, agronomy reports, input transactions or settlements. Those records
belong to the target site and must never be overwritten by an app upgrade.

ERPNext UOMs, Items, custom integration fields, accounting/inventory dimensions and permissions are
created idempotently by the app's install and migrate hooks. Company-specific accounts and defaults are
derived from the target site rather than copied from the development server.

## Install On Another Site

From the target bench:

```bash
bench get-app <repository-url> --branch <deployment-branch>
bench --site <site-name> install-app naseco_fieldopsbackend
bench --site <site-name> migrate
bench build --app naseco_fieldopsbackend
bench --site <site-name> clear-cache
```

Verify the completed installation:

```bash
bench --site <site-name> execute naseco_fieldopsbackend.deployment.verify_deployment
```

The returned `ready` value must be `true` before production rollout.

ERPNext must be installed and a Company with a Chart of Accounts should be configured before FieldOps
is used for stock, advances and settlement. Review **FieldOps Settings** after installation to confirm the
Company, Warehouses, Accounts, Mode of Payment and approver Users selected from the target site.

## Optional Demo Records

Production installation never imports test farmers or transactions. To create the explicit demonstration
dataset on a training site only, run:

```bash
bench --site <site-name> execute naseco_fieldopsbackend.fixtures.seed_data.execute_demo
```

## Maintaining The Bundle

After changing an app-owned standard on the development site, update the allow-list in
`naseco_fieldopsbackend/deployment.py`, then export and validate:

```bash
bench --site <development-site> export-fixtures --app naseco_fieldopsbackend
python -m unittest naseco_fieldopsbackend.test_deployment
```

Do not add transactional DocTypes to `FIXTURES`. New company-dependent ERPNext records should be handled
by an idempotent setup function instead of exporting records from a live site.
