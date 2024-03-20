# How to set up language files

Inspired by https://phrase.com/blog/posts/i18n-advantages-babel-python/#Integration_with_Jinja2_templates

Add translate statements to jinja2 templates

```
<title>{% trans %}Page title{% endtrans %}</title>
```

To parse the jinja templates to extract the messages, first 
create a file named `babel-mapping.ini`:

```
[python: **.py]
[jinja2: **/templates/**.html]
extensions=jinja2.ext.i18n,jinja2.ext.autoescape,jinja2.ext.with_
```

Then extract the base messages from templates:
> pybabel extract -F babel-mapping.ini -o locale/messages.pot ./

This file is not persisted on github.

If the above command gives this ouput:
```
AttributeError: module 'jinja2.ext' has no attribute 'autoescape'
```

Just comment out the extensions line in the `babel-mapping.ini` file:
```
[python: **.py]
[jinja2: **/templates/**.html]
;extensions=jinja2.ext.i18n,jinja2.ext.autoescape,jinja2.ext.with_
```

Then rerun the command for extracting base messages.


Now setup a new language (french) using the init command:
> pybabel init -d locale -l fr -i locale/messages.pot

Or update an existing language using:
> pybabel update -d locale -l fr -i locale/messages.pot

Run compile command to generate MO files:
> pybabel compile -d locale -l fr
