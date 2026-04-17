from common.models import AuditLog


class AuditService:
    @staticmethod
    def log(action, instance, payload=None, user=None):
        return AuditLog.objects.create(
            action=action,
            model=instance.__class__.__name__,
            object_id=str(instance.pk or 'unsaved'),
            payload=payload or {},
            user=user,
        )

    @staticmethod
    def log_custom(action, model, object_id, payload=None, user=None):
        return AuditLog.objects.create(
            action=action,
            model=model,
            object_id=str(object_id),
            payload=payload or {},
            user=user,
        )