#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) Pootle contributors.
#
# This file is a part of the Pootle project. It is distributed under the GPL3
# or later license. See the LICENSE file for a copy of the license and the
# AUTHORS file for copyright and authorship information.

from django.core import checks
from django.utils.translation import ugettext as _


# Minimum Redis server version required.
# Initially set to some minimums based on:
# 1. Ubuntu 12.04LTS's version 2.8.4 (10.04LTS was too old for RQ)
# 2. RQ requires >= 2.6.0, and
# 3. Wanting to insist on at least the latest stable that devs are using i.e.
#    2.8.* versions of Redis
REDIS_MINIMUM_REQUIRED_VERSION = (2, 8, 4)


@checks.register()
def test_redis(app_configs, **kwargs):
    from django_rq.queues import get_queue
    from django_rq.workers import Worker

    errors = []

    try:
        queue = get_queue()
        workers = Worker.all(queue.connection)
    except Exception as e:
        conn_settings = queue.connection.connection_pool.connection_kwargs
        errors.append(checks.Critical(_("Could not connect to Redis (%s)") % (e),
            hint=_("Make sure Redis is running on %(host)s:%(port)s") % (conn_settings),
            id="pootle.C001",
        ))
    else:
        if not workers or workers[0].stopped:
            errors.append(checks.Warning(_("No RQ Worker running."),
                hint=_("Run new workers with manage.py rqworker"),
                id="pootle.W001",
            ))

        redis_version = queue.connection.info()["redis_version"].split(".")
        if tuple(int(x) for x in redis_version) < REDIS_MINIMUM_REQUIRED_VERSION:
            errors.append(checks.Warning(_("Your version of Redis is too old."),
                hint=_("Update your system's Redis server package"),
                id="pootle.W002",
            ))

    return errors