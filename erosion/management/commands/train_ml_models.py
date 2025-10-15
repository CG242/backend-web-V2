"""
Commande Django pour l'entraînement des modèles ML
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction
import logging

from erosion.models import ModeleML
from erosion.ml_services import MLTrainingService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Entraîne les modèles ML pour la prédiction d\'érosion'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force l\'entraînement même s\'il y a déjà des modèles actifs',
        )
        parser.add_argument(
            '--models',
            nargs='+',
            choices=['random_forest', 'regression_lineaire', 'all'],
            default=['all'],
            help='Types de modèles à entraîner (défaut: all)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Affichage détaillé des logs',
        )

    def handle(self, *args, **options):
        """Point d'entrée de la commande"""
        self.verbosity = 2 if options['verbose'] else 1
        force = options['force']
        models_to_train = options['models']
        
        self.stdout.write(
            self.style.SUCCESS(
                f'=== ENTRAÎNEMENT DES MODÈLES ML - {timezone.now().strftime("%Y-%m-%d %H:%M:%S")} ==='
            )
        )
        
        try:
            # Vérifier les prérequis
            self._check_prerequisites(force)
            
            # Initialiser le service d'entraînement
            training_service = MLTrainingService()
            
            # Entraîner les modèles
            results = self._train_models(training_service, models_to_train)
            
            # Afficher les résultats
            self._display_results(results)
            
            self.stdout.write(
                self.style.SUCCESS('✅ Entraînement terminé avec succès!')
            )
            
        except Exception as e:
            logger.error(f"Erreur lors de l'entraînement: {e}")
            raise CommandError(f'Erreur lors de l\'entraînement: {e}')

    def _check_prerequisites(self, force):
        """Vérifie les prérequis pour l'entraînement"""
        self.stdout.write('🔍 Vérification des prérequis...')
        
        # Vérifier s'il y a des données d'entraînement
        from erosion.models import HistoriqueErosion, Zone
        
        total_zones = Zone.objects.count()
        total_historique = HistoriqueErosion.objects.count()
        
        if total_zones == 0:
            raise CommandError('Aucune zone trouvée. Créez des zones avant l\'entraînement.')
        
        if total_historique < 10:
            raise CommandError(
                f'Pas assez de données historiques ({total_historique}). '
                f'Minimum 10 mesures d\'érosion requises pour l\'entraînement.'
            )
        
        # Vérifier les modèles existants
        active_models = ModeleML.objects.filter(statut='actif').count()
        if active_models > 0 and not force:
            self.stdout.write(
                self.style.WARNING(
                    f'⚠️  {active_models} modèle(s) actif(s) trouvé(s). '
                    f'Utilisez --force pour forcer l\'entraînement.'
                )
            )
            raise CommandError('Modèles actifs existants. Utilisez --force pour continuer.')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'✅ Prérequis OK: {total_zones} zones, {total_historique} mesures historiques'
            )
        )

    def _train_models(self, training_service, models_to_train):
        """Entraîne les modèles spécifiés"""
        self.stdout.write('🤖 Début de l\'entraînement des modèles...')
        
        with transaction.atomic():
            # Marquer tous les modèles existants comme inactifs
            ModeleML.objects.filter(statut='actif').update(statut='inactif')
            
            # Entraîner les modèles
            results = training_service.train_models()
            
            # Vérifier les résultats
            if results.get('errors'):
                error_msg = 'Erreurs lors de l\'entraînement:\n' + '\n'.join(results['errors'])
                raise CommandError(error_msg)
            
            return results

    def _display_results(self, results):
        """Affiche les résultats de l'entraînement"""
        self.stdout.write('\n📊 RÉSULTATS DE L\'ENTRAÎNEMENT:')
        self.stdout.write('=' * 50)
        
        # Random Forest
        if results.get('random_forest'):
            rf_result = results['random_forest']
            if 'error' in rf_result:
                self.stdout.write(
                    self.style.ERROR(f'❌ Random Forest: {rf_result["error"]}')
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✅ Random Forest: R² = {rf_result["r2_score"]:.3f}, '
                        f'MSE = {rf_result["mse"]:.3f}'
                    )
                )
                if self.verbosity >= 2:
                    self.stdout.write(f'   Modèle ID: {rf_result["model_id"]}')
                    self.stdout.write(f'   Fichier: {rf_result["model_path"]}')
        
        # Régression Linéaire
        if results.get('regression_lineaire'):
            lr_result = results['regression_lineaire']
            if 'error' in lr_result:
                self.stdout.write(
                    self.style.ERROR(f'❌ Régression Linéaire: {lr_result["error"]}')
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✅ Régression Linéaire: R² = {lr_result["r2_score"]:.3f}, '
                        f'MSE = {lr_result["mse"]:.3f}'
                    )
                )
                if self.verbosity >= 2:
                    self.stdout.write(f'   Modèle ID: {lr_result["model_id"]}')
                    self.stdout.write(f'   Fichier: {lr_result["model_path"]}')
        
        # Modèle actif
        active_model = ModeleML.objects.filter(statut='actif').first()
        if active_model:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n🎯 MODÈLE ACTIF: {active_model.nom} v{active_model.version}'
                )
            )
            self.stdout.write(f'   Type: {active_model.get_type_modele_display()}')
            self.stdout.write(f'   Précision: {active_model.precision_score:.3f}')
            self.stdout.write(f'   Features: {len(active_model.features_utilisees)}')
        else:
            self.stdout.write(
                self.style.WARNING('⚠️  Aucun modèle marqué comme actif')
            )
        
        # Statistiques générales
        total_models = ModeleML.objects.count()
        self.stdout.write(f'\n📈 STATISTIQUES:')
        self.stdout.write(f'   Total modèles: {total_models}')
        self.stdout.write(f'   Modèles actifs: {ModeleML.objects.filter(statut="actif").count()}')
        
        if self.verbosity >= 2:
            self._display_model_details()

    def _display_model_details(self):
        """Affiche les détails des modèles"""
        self.stdout.write('\n🔍 DÉTAILS DES MODÈLES:')
        self.stdout.write('-' * 30)
        
        models = ModeleML.objects.all().order_by('-date_creation')
        for model in models:
            status_icon = '🟢' if model.statut == 'actif' else '🔴'
            self.stdout.write(
                f'{status_icon} {model.nom} v{model.version} ({model.type_modele})'
            )
            self.stdout.write(f'   Statut: {model.get_statut_display()}')
            self.stdout.write(f'   Précision: {model.precision_score or "N/A"}')
            self.stdout.write(f'   Prédictions: {model.nombre_predictions}')
            self.stdout.write(f'   Créé: {model.date_creation.strftime("%Y-%m-%d %H:%M")}')
            if model.date_derniere_utilisation:
                self.stdout.write(f'   Dernière utilisation: {model.date_derniere_utilisation.strftime("%Y-%m-%d %H:%M")}')
            self.stdout.write('')
