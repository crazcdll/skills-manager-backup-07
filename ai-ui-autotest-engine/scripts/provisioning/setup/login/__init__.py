#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L1~L4 公共入口（外部只依赖本模块，不直接依赖内部实现）。"""
from provisioning.setup.login.orchestrator import execute_login
from provisioning.setup.login.plan import (
    DEFAULT_COUNTRY_CODE, DEFAULT_LOGIN_ENV, LoginPlan, SwimlineConfig,
    TARGET_ENV_ALPHA, TARGET_ENV_NONE, TARGET_ENV_ONLINE, TARGET_ENV_SWIMLINE,
)
from provisioning.setup.login.policy import (
    AuthOutcome, LoginContext, ProbeResult, ProvisionStep, RestartPolicy, StepOutcome,
)
from provisioning.setup.login.probes import (
    LOGIN_STATE_PROBES, LoginStateProbe, get_login_state_probe,
)
from provisioning.setup.login.registry import ENV_STEPS, EnvPipeline, build_pipeline

__all__ = [
    "execute_login",
    "LoginPlan", "SwimlineConfig",
    "DEFAULT_COUNTRY_CODE", "DEFAULT_LOGIN_ENV",
    "TARGET_ENV_ONLINE", "TARGET_ENV_ALPHA", "TARGET_ENV_SWIMLINE", "TARGET_ENV_NONE",
    "LoginContext", "RestartPolicy", "ProvisionStep", "StepOutcome", "AuthOutcome",
    "ProbeResult", "LoginStateProbe", "LOGIN_STATE_PROBES", "get_login_state_probe",
    "EnvPipeline", "ENV_STEPS", "build_pipeline",
]
