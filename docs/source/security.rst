.. _security:

Security
========

There exist use cases which require authentication and authorization against an API at various granularities
(collections, processes, etc.), restricting access to a given user, group or role.  Implementing security
can be as simple as HTTP basic authentication, or as complex as fine-grained access control against a specific
collection item.

By design, pygeoapi does not have built-in support for access control.  It is up to the user to secure pygeoapi
as required.

The following projects provide security frameworks atop pygeoapi:

* `fastgeoapi <https://github.com/geobeyond/fastgeoapi>`_
* `pygeoapi-auth-deployment <https://github.com/cartologic/pygeoapi-auth-deployment>`_
* `pygeoapi-auth <https://github.com/geopython/pygeoapi-auth>`_ (Python package for use along with pygeoapi-auth-deployment)
