"""Decision-policy construction shared by CLI, settings and embedded loops."""


PROVIDERS = ('jev', 'laya')


def decision_policy(provider, *, jev, laya_model='multilingual'):
    if provider == 'jev':
        from .controller import JevDecisionPolicy
        return JevDecisionPolicy(jev)
    if provider == 'laya':
        from .laya import LayaDecisionPolicy
        return LayaDecisionPolicy(model=laya_model)
    raise ValueError('Ungültiger Entscheidungsanbieter.')
