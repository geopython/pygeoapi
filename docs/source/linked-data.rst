.. _linked-data:

Linked Data
===========

.. image:: https://json-ld.org/images/json-ld-logo-64.png
    :width: 64px
    :align: left
    :alt: JSON-LD support

pygeoapi supports structured metadata about a deployed instance, and is also capable of presenting feature data as structured data. `JSON-LD <https://json-ld.org/>`_ equivalents are available for each HTML page, and are embedded as data blocks within the corresponding page for search engine optimisation (SEO). Tools such as the `Google Structured Data Testing Tool <https://search.google.com/structured-data/testing-tool#url=https%3A%2F%2Fdemo.pygeoapi.io%2Fmaster>`_ can be used to check the structured representations.

The metadata for an instance is determined by the content of the `metadata` section of the configuration YAML. This metadata is included automatically, and is sufficient for inclusion in major indices of datasets, including the `Google Dataset Search <https://developers.google.com/search/docs/data-types/dataset>`_.

For collections, at the level of an item or items, by default the JSON-LD representation adds:

- The GeoJSON JSON-LD `vocabulary and context <https://geojson.org/geojson-ld/>`_ to the ``@context``.
- An ``@id`` for each feature in a collection, that is the URL for that feature (resolving to its HTML representation in pygeoapi)

.. note:: While this is enough to provide valid RDF (as GeoJSON-LD), it does not allow the *properties* of your features to be unambiguously interpretable.

pygeoapi currently allows for the extension of the ``@context`` to allow properties to be aliased to terms from vocabularies. This is done by adding a ``context`` section to the configuration of a `dataset`.

The default pygeoapi configuration includes an example for the ``obs`` sample dataset:

.. code-block:: yaml

  context:
      - datetime: https://schema.org/DateTime
      - vocab: https://example.com/vocab#
        stn_id: "vocab:stn_id"
        value: "vocab:value"

This is a non-existent vocabulary included only to illustrate the expected data structure within the YAML configuration. In particular, the links for the ``stn_id`` and ``value`` properties do not resolve. We can extend this example to one with terms defined by schema.org:

.. code-block:: yaml

  context:
      - schema: https://schema.org/
        stn_id: schema:identifer
        datetime:
            "@id": schema:observationDate
            "@type": schema:DateTime
        value:
            "@id": schema:value
            "@type": schema:Number

Now this has been elaborated, the benefit of a structured data representation becomes clearer. What was once an unexplained property called ``datetime`` in the source CSV, it can now be `expanded <https://www.w3.org/TR/json-ld-api/#expansion-algorithms>`_ to `<https://schema.org/observationDate>`_, thereby eliminating ambiguity and enhancing interoperability. Its type is also expressed as `<https://schema.org/DateTime>`_.

This example demonstrates how to use this feature with a CSV data provider, using included sample data. The implementation of JSON-LD structured data is available for any data provider but is currently limited to defining a ``@context``. Relationships between features can be expressed but is dependent on such relationships being expressed by the dataset provider, not pygeoapi.


.. _`YAML`: https://en.wikipedia.org/wiki/YAML
