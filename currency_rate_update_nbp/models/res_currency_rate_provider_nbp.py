# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import json
import logging
from datetime import datetime

import requests

from odoo import fields, models


class ResCurrencyRateProviderNBP(models.Model):
    _inherit = "res.currency.rate.provider"

    service = fields.Selection(
        selection_add=[("NBP", "National Bank of Poland")],
        ondelete={"NBP": "set default"},
    )

    def _get_supported_currencies(self):
        """Return list of currencies supported by NBP"""
        self.ensure_one()
        if self.service != "NBP":
            return super()._get_supported_currencies()  # pragma: no cover

        # List of currencies obtained from NBP API
        return [
            "THB",
            "USD",
            "AUD",
            "HKD",
            "CAD",
            "NZD",
            "SGD",
            "EUR",
            "HUF",
            "CHF",
            "GBP",
            "UAH",
            "JPY",
            "CZK",
            "DKK",
            "ISK",
            "NOK",
            "SEK",
            "HRK",
            "RON",
            "BGN",
            "TRY",
            "ILS",
            "CLP",
            "PHP",
            "MXN",
            "ZAR",
            "BRL",
            "MYR",
            "RUB",
            "IDR",
            "INR",
            "KRW",
            "CNY",
            "XDR",
            "PLN",
        ]

    def _obtain_rates(self, base_currency, currencies, date_from, date_to):
        """Make request to NBP API and fetch rates for the date range"""
        self.ensure_one()
        if self.service != "NBP":
            return super()._obtain_rates(
                base_currency, currencies, date_from, date_to
            )  # pragma: no cover

        _logger = logging.getLogger(__name__)
        res = {}

        # NBP API base URL
        api_base = "https://api.nbp.pl/api/exchangerates/rates/a"

        # Get rates for each currency
        for curr in currencies:
            if curr == "PLN":
                # PLN is always 1.0 relative to itself
                continue

            try:
                # Request rates for this currency in the date range
                url = f"{api_base}/{curr.lower()}/{date_from}/{date_to}/"
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                
                # Process each rate in the response
                for rate_data in data.get('rates', []):
                    effective_date_str = rate_data.get('effectiveDate')
                    if not effective_date_str:
                        continue
                        
                    # Parse the date
                    try:
                        effective_date = datetime.strptime(effective_date_str, "%Y-%m-%d").date()
                    except ValueError:
                        _logger.warning(f"Invalid date format in NBP response: {effective_date_str}")
                        continue
                    
                    # Initialize date entry if not exists
                    if effective_date not in res:
                        res[effective_date] = {}
                    
                    # Get the mid rate
                    mid_rate = rate_data.get('mid')
                    if mid_rate is not None:
                        # For now, store rates relative to PLN
                        res[effective_date][curr] = mid_rate
                        # Also set PLN rate if not set
                        if "PLN" not in res[effective_date]:
                            res[effective_date]["PLN"] = 1.0

            except requests.RequestException as e:
                _logger.warning(f"Failed to fetch rates for currency {curr}: {e}")
                continue
            except json.JSONDecodeError as e:
                _logger.warning(f"Failed to parse JSON response for currency {curr}: {e}")
                continue
            except KeyError as e:
                _logger.warning(f"Unexpected JSON structure for currency {curr}: {e}")
                continue

        # Handle base currency conversion if needed
        if base_currency != "PLN":
            # Get base currency rates
            try:
                url = f"{api_base}/{base_currency.lower()}/{date_from}/{date_to}/"
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                base_data = response.json()
                
                # Create a mapping of dates to base currency rates
                base_rates = {}
                for rate_data in base_data.get('rates', []):
                    effective_date_str = rate_data.get('effectiveDate')
                    if effective_date_str:
                        try:
                            effective_date = datetime.strptime(effective_date_str, "%Y-%m-%d").date()
                            base_rates[effective_date] = rate_data.get('mid', 1.0)
                        except ValueError:
                            continue
                
                # Convert all rates to base currency
                for date_key, rates in res.items():
                    base_rate = base_rates.get(date_key, 1.0)
                    for curr in list(rates.keys()):
                        if curr != "PLN" and curr != base_currency:
                            rates[curr] = rates[curr] / base_rate
                    rates[base_currency] = 1.0
                    
            except Exception as e:
                _logger.warning(f"Failed to get base currency rates for {base_currency}: {e}")

        return res