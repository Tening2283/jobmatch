from rest_framework import permissions


class IsCandidate(permissions.BasePermission):
    message = "Réservé aux candidats."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_candidate)


class IsRecruiter(permissions.BasePermission):
    message = "Réservé aux recruteurs."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_recruiter or request.user.is_staff)
        )


class IsOwnerOrReadOnly(permissions.BasePermission):
    """L'objet doit exposer `owner_id` (ou `recruiter_id`)."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        owner_id = getattr(obj, "recruiter_id", None) or getattr(obj, "owner_id", None)
        return request.user.is_staff or owner_id == request.user.id
