import django_filters
from .models import (
    Zone, Capteur, Mesure, Prediction, Alerte, 
    HistoriqueErosion, TendanceLongTerme, EvenementClimatique
)


class ZoneFilter(django_filters.FilterSet):
    """Filtres pour le modèle Zone"""
    nom = django_filters.CharFilter(lookup_expr='icontains')
    niveau_risque = django_filters.ChoiceFilter(choices=Zone._meta.get_field('niveau_risque').choices)
    superficie_min = django_filters.NumberFilter(field_name='superficie_km2', lookup_expr='gte')
    superficie_max = django_filters.NumberFilter(field_name='superficie_km2', lookup_expr='lte')
    
    class Meta:
        model = Zone
        fields = ['nom', 'niveau_risque', 'superficie_min', 'superficie_max']


class CapteurFilter(django_filters.FilterSet):
    """Filtres pour le modèle Capteur"""
    nom = django_filters.CharFilter(lookup_expr='icontains')
    type = django_filters.ChoiceFilter(choices=Capteur._meta.get_field('type').choices)
    etat = django_filters.ChoiceFilter(choices=Capteur._meta.get_field('etat').choices)
    zone = django_filters.ModelChoiceFilter(queryset=Zone.objects.all())
    
    class Meta:
        model = Capteur
        fields = ['nom', 'type', 'etat', 'zone']


class MesureFilter(django_filters.FilterSet):
    """Filtres pour le modèle Mesure"""
    capteur = django_filters.ModelChoiceFilter(queryset=Capteur.objects.all())
    zone = django_filters.ModelChoiceFilter(queryset=Zone.objects.all(), field_name='capteur__zone')
    type_capteur = django_filters.ChoiceFilter(choices=Capteur._meta.get_field('type').choices, field_name='capteur__type')
    qualite_donnee = django_filters.ChoiceFilter(choices=Mesure._meta.get_field('qualite_donnee').choices)
    valeur_min = django_filters.NumberFilter(field_name='valeur', lookup_expr='gte')
    valeur_max = django_filters.NumberFilter(field_name='valeur', lookup_expr='lte')
    date_debut = django_filters.DateTimeFilter(field_name='timestamp', lookup_expr='gte')
    date_fin = django_filters.DateTimeFilter(field_name='timestamp', lookup_expr='lte')
    
    class Meta:
        model = Mesure
        fields = ['capteur', 'zone', 'type_capteur', 'qualite_donnee', 'valeur_min', 'valeur_max', 'date_debut', 'date_fin']


class PredictionFilter(django_filters.FilterSet):
    """Filtres pour le modèle Prediction"""
    zone = django_filters.ModelChoiceFilter(queryset=Zone.objects.all())
    modele_utilise = django_filters.CharFilter(lookup_expr='icontains')
    horizon_min = django_filters.NumberFilter(field_name='horizon_jours', lookup_expr='gte')
    horizon_max = django_filters.NumberFilter(field_name='horizon_jours', lookup_expr='lte')
    confiance_min = django_filters.NumberFilter(field_name='confiance_pourcentage', lookup_expr='gte')
    confiance_max = django_filters.NumberFilter(field_name='confiance_pourcentage', lookup_expr='lte')
    
    class Meta:
        model = Prediction
        fields = ['zone', 'modele_utilise', 'horizon_min', 'horizon_max', 'confiance_min', 'confiance_max']


class AlerteFilter(django_filters.FilterSet):
    """Filtres pour le modèle Alerte"""
    zone = django_filters.ModelChoiceFilter(queryset=Zone.objects.all())
    type = django_filters.ChoiceFilter(choices=Alerte._meta.get_field('type').choices)
    niveau = django_filters.ChoiceFilter(choices=Alerte._meta.get_field('niveau').choices)
    est_resolue = django_filters.BooleanFilter()
    titre = django_filters.CharFilter(lookup_expr='icontains')
    
    class Meta:
        model = Alerte
        fields = ['zone', 'type', 'niveau', 'est_resolue', 'titre']


class HistoriqueErosionFilter(django_filters.FilterSet):
    """Filtres pour le modèle HistoriqueErosion"""
    zone = django_filters.ModelChoiceFilter(queryset=Zone.objects.all())
    methode_mesure = django_filters.ChoiceFilter(choices=HistoriqueErosion._meta.get_field('methode_mesure').choices)
    taux_min = django_filters.NumberFilter(field_name='taux_erosion_m_an', lookup_expr='gte')
    taux_max = django_filters.NumberFilter(field_name='taux_erosion_m_an', lookup_expr='lte')
    date_debut = django_filters.DateTimeFilter(field_name='date_mesure', lookup_expr='gte')
    date_fin = django_filters.DateTimeFilter(field_name='date_mesure', lookup_expr='lte')
    
    class Meta:
        model = HistoriqueErosion
        fields = ['zone', 'methode_mesure', 'taux_min', 'taux_max', 'date_debut', 'date_fin']


class TendanceLongTermeFilter(django_filters.FilterSet):
    """Filtres pour le modèle TendanceLongTerme"""
    zone = django_filters.ModelChoiceFilter(queryset=Zone.objects.all())
    tendance = django_filters.ChoiceFilter(choices=TendanceLongTerme._meta.get_field('tendance').choices)
    taux_min = django_filters.NumberFilter(field_name='taux_erosion_moyen_m_an', lookup_expr='gte')
    taux_max = django_filters.NumberFilter(field_name='taux_erosion_moyen_m_an', lookup_expr='lte')
    
    class Meta:
        model = TendanceLongTerme
        fields = ['zone', 'tendance', 'taux_min', 'taux_max']


class EvenementClimatiqueFilter(django_filters.FilterSet):
    """Filtres pour le modèle EvenementClimatique"""
    nom = django_filters.CharFilter(lookup_expr='icontains')
    type = django_filters.ChoiceFilter(choices=EvenementClimatique._meta.get_field('type').choices)
    intensite = django_filters.ChoiceFilter(choices=EvenementClimatique._meta.get_field('intensite').choices)
    zones_impactees = django_filters.ModelMultipleChoiceFilter(queryset=Zone.objects.all())
    date_debut_min = django_filters.DateTimeFilter(field_name='date_debut', lookup_expr='gte')
    date_debut_max = django_filters.DateTimeFilter(field_name='date_debut', lookup_expr='lte')
    
    class Meta:
        model = EvenementClimatique
        fields = ['nom', 'type', 'intensite', 'zones_impactees', 'date_debut_min', 'date_debut_max']
