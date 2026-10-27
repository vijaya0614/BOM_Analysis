"""Nexar GraphQL query strings. Keep all GraphQL here — do not scatter strings."""

SEARCH_MPN = """
query SearchMpn($q: String!, $limit: Int, $country: String, $currency: String) {
  supSearchMpn(q: $q, limit: $limit, country: $country, currency: $currency) {
    hits
    results {
      description
      part {
        mpn
        name
        shortDescription
        manufacturer { name }
        category { name }
        bestDatasheet { url name }
        specs { attribute { name } displayValue value }
        sellers {
          company { name }
          country
          offers {
            inventoryLevel
            moq
            factoryLeadDays
            packaging
            prices { quantity price currency convertedPrice convertedCurrency }
          }
        }
        similarParts { mpn manufacturer { name } }
      }
    }
  }
}
"""

MULTI_MATCH = """
query MultiMatch($queries: [SupMatchQuery!]!, $country: String, $currency: String) {
  supMultiMatch(queries: $queries, country: $country, currency: $currency) {
    hits
    parts {
      mpn
      name
      shortDescription
      manufacturer { name }
      category { name }
      bestDatasheet { url name }
      specs { attribute { name } displayValue value }
      sellers {
        company { name }
        country
        offers {
          inventoryLevel
          moq
          factoryLeadDays
          packaging
          prices { quantity price currency convertedPrice convertedCurrency }
        }
      }
      similarParts { mpn manufacturer { name } }
    }
  }
}
"""
