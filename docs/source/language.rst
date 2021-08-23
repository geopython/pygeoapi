.. _language:

Multilingual support
====================

pygeoapi is language-aware and can handle multiple languages if these have been defined in pygeoapi's configuration (see `maintainer guide`_).
Providers can also handle multiple languages if configured. These may even be different from the languages that pygeoapi
supports. Out-of-the-box, pygeoapi "speaks" English. System messages and exceptions are always English only.

The following sections provide more information how to use and set up languages in pygeoapi.

End user guide
--------------

There are 2 ways to affect the language of the results returned by pygeoapi, both for the HTML and JSON(-LD) formats:

1. After the requested pygeoapi URL, append a ``lang=<code>`` query parameter, where ``<code>`` should be replaced by a well-known language code.
   This can be an ISO 639-1 code (e.g. `de` for German), optionally accompanied by an ISO 3166-1 alpha-2 country code (e.g. `de-CH` for Swiss-German).
   Please refer to this `W3C article <https://www.w3.org/International/articles/language-tags/>`_ for more information or
   this `list of language codes <http://www.lingoes.net/en/translator/langcode.htm>`_ for more examples.
   Another option is to send a complex definition with quality weights (e.g. `de-CH, de;q=0.9, en;q=0.8, fr;q=0.7, \*;q=0.5`).
   pygeoapi will then figure out the best match for the requested language.

   For example, to view the pygeoapi landing page in Canadian-French, you could use this URL:

   https://demo.pygeoapi.io/master?lang=fr-CA

2. Alternatively, you can set an ``Accept-Language`` HTTP header for the requested pygeoapi URL. Language tags that are valid for
   the ``lang`` query parameter are also valid for this header value.
   Please note that if your client application (e.g. browser) is configured for a certain language, it will likely set this
   header by default, so the returned response should be translated to the language of your client app. If you don't want this,
   you can either change the language of your client app or append the ``lang`` parameter to the URL, which will override
   any language defined in the ``Accept-Language`` header.


Notes
^^^^^

- If pygeoapi cannot find a good match to the requested language, the response is returned in the default language (US English mostly).
  The default language is the *first* language defined in pygeoapi's server configuration YAML (see `maintainer guide`_).

- Even if pygeoapi *itself* supports the requested language, provider plugins may not support that particular language or perhaps don't even
  support any language at all. In that case the provider will reply in its own "unknown" language, which may not be the same language
  as the default pygeoapi server language set in the ``Content-Language`` HTTP response header.

- It is up to the creator of the provider to properly define at least 1 supported language in the provider configuration, as described
  in the `developer guide`_. This will ensure that the ``Content-Language`` HTTP response header is always set properly.

- If pygeoapi found a match to the requested language, the response will include a ``Content-Language`` HTTP header,
  set to the best-matching server language code. This is the default behavior for most pygeoapi requests. However, note that some responses
  (e.g. exceptions) always have a ``Content-Language: en-US`` header, regardless of the requested language.

- For results returned by a **provider**, the ``Content-Language`` HTTP header will be set to the best-matching
  provider language or the best-matching pygeoapi server language if the provider is not language-aware.

- If the provider supports a requested language, but pygeoapi does *not* support that same language, the ``Content-Language``
  header will contain both the provider language *and* the best-matching pygeoapi server language.

- Please note that the ``Content-Language`` HTTP response header only *indicates the language of the intended audience*.
  It does not necessarily mean that the content is actually written in that particular language.


Maintainer guide
----------------

Every pygeoapi instance should support at least 1 language. In the server configuration, there must be a ``language``
or a ``languages`` (note the `s`) property. The property can be set to a single language tag or a list of tags respectively.

If you wish to set up a multilingual pygeoapi instance, you will have to add more than 1 language to the
server configuration YAML file (i.e. ``pygeoapi-config.yml``). First, you will have to add the supported language tags/codes
as a list. For example, if you wish to support American English and Canadian French, you could do:

.. code-block:: yaml

   server:
       bind: ...
       url: ...
       mimetype: ...
       encoding: ...
       languages:
           - en-US
           - fr-CA

Next, you will have to provide translations for the configured languages. This involves 3 steps:

1. `Add translations for configurable text values`_ in the server YAML file;

2. Verify if there are any Jinja2 HTML template translations for the configured language(s);

3. Make sure that the provider plugins you need can handle this language as well, if you have the ability to do so.
   See the `developer guide`_ for more details.


Notes
^^^^^

- The **first** language you define in the configuration determines the default language, i.e. the language that pygeoapi will
  use if no other language was requested or no best match for the requested language could be found.

- It is not possible to **disable** language support in pygeoapi. The functionality is always on and a ``Content-Language``
  HTTP response header is always set. If results should be available in a single language, you'd have to set that language only
  in the pygeoapi configuration.

- Results returned from a provider may be in a different language than pygeoapi's own server language. The "raw" requested language
  is always passed on to the provider, even if pygeoapi itself does not support it. For more information, see the `end user guide`_
  and the `developer guide`_.


Add translations for configurable text values
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

For most of the text values in pygeoapi's server configuration where it makes sense, you can add translations.
Consider the ``metadata`` section for example. The English-only version looks similar to this:

.. code-block:: yaml

   metadata:
       identification:
           title: pygeoapi default instance
           description: pygeoapi provides an API to geospatial data
           keywords:
               - geospatial
               - data
               - api

If you wish to make these text values available in English and French, you could use the following language struct:

.. code-block:: yaml

   metadata:
       identification:
           title:
               en: pygeoapi default instance
               fr: instance par défaut de pygeoapi
           description:
               en: pygeoapi provides an API to geospatial data
               fr: pygeoapi fournit une API aux données géospatiales
           keywords:
               en:
                   - geospatial
                   - data
                   - api
               fr:
                   - géospatiale
                   - données
                   - api

In other words: each plain text value should be replaced by a dictionary, where the language code is the key and the translated text represents the matching value.
For lists, this can be applied as well (see ``keywords`` example above), as long as you nest the entire list under a language key instead of each list item.

Note that the example above uses generic language tags, but you can also supply more localized tags (with a country code) if required.
pygeoapi should always be able find the best match to the requested language, i.e. if the user wants Swiss-French (`fr-CH`) but pygeoapi can only find `fr` tags,
those values will be returned. However, if a `fr-CH` tag can also be found, that value will be returned and not the `fr` value.

.. todo::   Add docs on HTML templating.

Translator guide
----------------

Hardcoded strings in pygeoapi templates are translated using the Babel translation system.
Translation files are stored on the /locale folder.
Translators can follow these steps to prepare their environment for translations.


1. Extract from latest code the keys to be translated. These keys are captured in a .pot file.

   .. code-block:: bash

      pybabel extract -F babel-mapping.ini -o locale/messages.pot ./

2. Update the existing .po language file: 

   .. code-block:: bash

      pybabel update -d locale -l fr -i locale/messages.pot

3. Open the relevant .po file and contribute your translations. Then compile a .mo file to be used by the application: 

   .. code-block:: bash

      pybabel compile -d locale -l fr

Within jinja templates keys are prepared to be translated by wrapping them in: 

   .. code-block:: python

      {% trans %}Key{% endtrans %}


Developer guide
---------------

If you are a developer who wishes to create a pygeoapi provider plugin that "speaks" a certain language,
you will have to fully implement this yourself. Needless to say, if your provider depends on some backend, it will only make sense to
implement language support if the backend can be queried in another language as well.

You are free to set up the language support anyway you like, but there are a couple of steps you'll have to walk through:

1. You will have to define the supported languages in the provider configuration YAML. This can be done in a similar fashion
   as the ``languages`` configuration for pygeoapi itself, as described in the `maintainer guide`_ section above.
   For example, a TinyDB records provider that supports English and French could be set up like:

   .. code-block:: yaml

      my-records:
          type: collection
          ..
          providers:
              - type: record
                name: TinyDBCatalogue
                data: ..
                languages:
                    - en
                    - fr

2. If your provider implements any of the ``query``, ``get`` or ``get_metadata`` methods of the base class and you wish
   to make them language-aware, either add an implicit ``**kwargs`` parameter or an explicit ``language=None`` parameter
   to the method signature.

An example Python code block for a custom provider with a language-aware ``query`` method could look like this:

.. code-block:: python

   class MyCoolVectorDataProvider(BaseProvider):
   """My cool vector data provider"""

   def __init__(self, provider_def):
       super().__init__(provider_def)

   def query(self, startindex=0, limit=10, resulttype='results', bbox=[],
             datetime_=None, properties=[], sortby=[], select_properties=[],
             skip_geometry=False, q=None, language=None):
       LOGGER.debug(f'Provider queried in {language.english_name} language')
       # Implement your logic here, returning JSON in the requested language

Alternatively, you could also use ``**kwargs`` in the ``query`` method and get the ``language`` value:

.. code-block:: python

   def query(self, **kwargs):
       LOGGER.debug(f"Provider locale set to: {kwargs.get('language')}")
       # Implement your logic here, returning JSON in the requested language

This is all that is required. The pygeoapi API class will make sure that the correct HTTP ``Content-Language`` headers are set on the response object.

Notes
^^^^^

- If your provider implements any of the aforementioned ``query``, ``get`` and ``get_metadata`` methods,
  it **must** add a ``**kwargs`` or ``language=None`` parameter, even if it does not need to use the language parameter.

- Contrary to the pygeoapi server configuration, adding a ``language`` or ``languages`` (both are supported) property to the
  provider definition is **not** required and may be omitted. In that case, the passed-in ``language`` parameter language-aware provider methods
  (``query``, ``get``, etc.) will be set to ``None``. This results in the following behavior:

  - HTML responses returned from the providers will have the ``Content-Language`` header set to the best-matching pygeoapi server language.
  - JSON(-LD) responses returned from providers will **not** have a ``Content-Language`` header if ``language`` is ``None``.

- If the provider supports a requested language, the passed-in ``language`` will be set to the best matching
  `Babel Locale instance <http://babel.pocoo.org/en/latest/api/core.html#babel.core.Locale>`_.
  Note that this may be the provider default language if no proper match was found.
  No matter the output format, API responses returned from providers will always contain a best-matching ``Content-Language``
  header if one ore more supported provider languages were defined.

- For general information about building plugins, please visit the :ref:`plugins` page.
