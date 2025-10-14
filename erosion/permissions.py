from rest_framework import permissions


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Permission personnalisée pour permettre seulement aux propriétaires d'un objet de le modifier.
    """
    def has_object_permission(self, request, view, obj):
        # Permissions de lecture pour toute requête
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Permissions d'écriture seulement pour le propriétaire
        return obj.utilisateur == request.user


class IsAdminOrScientifique(permissions.BasePermission):
    """
    Permission pour les administrateurs et scientifiques seulement.
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        return request.user.role in ['admin', 'scientifique']


class IsAdminOrTechnicien(permissions.BasePermission):
    """
    Permission pour les administrateurs et techniciens seulement.
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        return request.user.role in ['admin', 'technicien']


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Permission pour les administrateurs (écriture) ou lecture seule pour les autres.
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        if request.method in permissions.SAFE_METHODS:
            return True
        
        return request.user.role == 'admin'


class CanManageCapteurs(permissions.BasePermission):
    """
    Permission pour gérer les capteurs (admin, scientifique, technicien).
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        return request.user.role in ['admin', 'scientifique', 'technicien']


class CanViewData(permissions.BasePermission):
    """
    Permission pour consulter les données (tous les utilisateurs authentifiés).
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated
