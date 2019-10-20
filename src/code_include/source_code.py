#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The module responsible for getting the code that this extension displays."""

import os
import urllib2

import bs4
import six

from . import error_classes
from . import helper

APPLICATION = None


@helper.memoize
def _get_all_intersphinx_roots():
    """set[str]: Every file path / URL that the user added to intersphinx's inventory."""
    roots = set()

    try:
        mappings = APPLICATION.config.intersphinx_mapping.items()
    except AttributeError:
        raise EnvironmentError("sphinx.ext.intersphinx was not configured properly.")

    for key, value in mappings:
        if not isinstance(value, six.string_types):
            roots.add(list(value)[0])
        else:
            roots.add(key)

    return roots


def _get_app_inventory():
    """dict[str, dict[str, tuple[str, str, str, str]]]: Get all cached targets + namespaces."""
    if not APPLICATION:
        return dict()

    try:
        return APPLICATION.builder.env.intersphinx_inventory
    except AttributeError:
        raise EnvironmentError("sphinx.ext.intersphinx was not configured properly.")


def _get_module_tag(namespace, directive):
    """Get the project-relative path to some Python class, method, or function.

    Args:
        namespace (str):
            The importable Python location of some class, method, or function.
            Example: "foo.bar.ClassName.get_method_data".
        directive (str):
            The Python type that `namespace` is. Example: "py:method".

    Returns:
        str:
            The exact path, relative to a Sphinx project's root directory,
            where this module is tagged.

    """
    tokens = namespace.split(".")

    if directive in {"py:method"}:
        base = "/".join(tokens[:-2])

        return "_modules/{base}.html".format(base=base), ".".join(tokens[-2:])

    base = "/".join(tokens[:-1])

    return "_modules/{base}.html".format(base=base), tokens[-1]


def _get_project_url_root(uri, roots):
    """Find the top-level project for some URL / file-path.

    Note:
        The matching `uri` must match an item `roots` exactly.

    Args:
        uri (str):
            The URL / file-path that presumably came from an intersphinx inventory
            file. This path is inside some Sphinx project (which we will find the root of).
        roots (iter[str]):
            Potential file paths / URLs that `uri` is a child of.

    Returns:
        str: The found root. If no root was found, return an empty string.

    """
    for root in roots:
        if uri.startswith(root):
            return root

    return ""


def _get_source_code(uri, tag):
    """Find the exact code for some class, method, attribute, or function.

    Args:
        uri (str):
            The URL / file-path to a HTML file that has Python
            source-code. is function scrapes the HTML file and returns
            the found source-code.
        tag (str):
            The class, method, attribute, or function that will be
            extracted from `uri`.

    Raises:
        :class:`.NotFoundFile`:
            If `uri` is a path to an HTML file but the file does not exist.
        :class:`.NotFoundUrl`:
            If `uri` is a URL and it could not be read properly.

    Returns:
        str:
            The found source-code. This text is returned as raw text
            (no HTML tags are included).

    """
    if os.path.isabs(uri):
        if not os.path.isfile(uri):
            raise error_classes.NotFoundFile(uri)

        with open(uri, "r") as handler:
            contents = handler.read()
    else:
        try:
            contents = urllib2.urlopen(uri).read()
        except Exception:
            raise error_classes.NotFoundUrl(uri)

    soup = bs4.BeautifulSoup(contents, "html.parser")

    for div in soup.find_all("a", {"class": "viewcode-back"}):
        div.decompose()

    node = soup.find("div", {"id": tag})

    return node.getText()


def get_source_code(directive, namespace):
    """Get the raw code of some class, method, attribute, or function.

    Args:
        directive (str):
            The Python type that `namespace` is. Example: "py:method".
        namespace (str):
            The importable Python location of some class, method, or function.
            Example: "foo.bar.ClassName.get_method_data".

    Raises:
        RuntimeError:
            If no intersphinx inventory cache could be found.
        :class:`.MissingDirective`:
            If `directive` wasn't found in any Sphinx project in the
            intersphinx inventory cache.
        :class:`.MissingNamespace`:
            If `directive` was in the intersphinx inventory cache but
            the no `namespace` could be found in any Sphinx project in
            the intersphinx inventory cache.
        EnvironmentError:
            If `directive` and `namespace` were both found properly but,
            for some reason, the top-level website / file path for the
            Sphinx project stored by intersphinx could not be found.

    Returns:
        str: The found source-code for `namespace`, with a type of `directive`.

    """
    cache = _get_app_inventory()

    if not cache:
        raise RuntimeError(
            "No application could be found. Cannot render this node. Did intersphinx have a chance to run?"
        )

    try:
        typed_directive_data = cache[directive]
    except KeyError:
        raise error_classes.MissingDirective(
            'Directive "{directive}" was invalid. Options were, "{options}".'.format(
                directive=directive, options=sorted(cache)
            )
        )

    try:
        _, _, uri, _ = typed_directive_data[namespace]
    except KeyError:
        raise error_classes.MissingNamespace(
            'Namespace "{namespace}" was invalid. Options were, "{options}".'.format(
                namespace=namespace, options=sorted(typed_directive_data)
            )
        )

    url, tag = uri.split("#")  # `url` might be a file path or web URL
    available_roots = _get_all_intersphinx_roots()
    root = _get_project_url_root(url, available_roots)

    if not root:
        raise EnvironmentError(
            'URL "{url}" isn\'t in any of the available projects, "{roots}".'.format(
                url=url, roots=sorted(available_roots)
            )
        )

    module_path, tag = _get_module_tag(tag, directive)
    module_url = root + "/" + module_path

    return _get_source_code(module_url, tag)
