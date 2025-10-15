// JavaScript pour l'envoi d'alertes dans l'interface admin Django
function envoyerAlerte(alerteId) {
    if (confirm('Êtes-vous sûr de vouloir envoyer cette alerte au frontend ?')) {
        // Afficher un indicateur de chargement
        const button = event.target;
        const originalText = button.innerHTML;
        button.innerHTML = '⏳ Envoi...';
        button.disabled = true;
        
        console.log('Envoi de l\'alerte ID:', alerteId);
        
        // Envoyer la requête au frontend
        fetch('/api/alertes/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                'alerte_id': alerteId,
                'destination': 'frontend'  // Indiquer que c'est pour le frontend
            }),
            timeout: 10000  // Timeout de 10 secondes
        })
        .then(response => {
            console.log('Réponse reçue:', response.status);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Données reçues:', data);
            if (data.success && data.sent) {
                // Envoi réussi - pas de message, juste changer le bouton
                button.innerHTML = '✅ Envoyée';
                button.style.backgroundColor = '#6c757d';
            } else {
                // Erreur - afficher le message d'erreur
                alert('❌ Erreur lors de l\'envoi:\n' + data.message);
                button.innerHTML = originalText;
                button.disabled = false;
            }
        })
        .catch(error => {
            console.error('Erreur détaillée:', error);
            alert('❌ Erreur de connexion: ' + error.message + '\n\nVérifiez que le serveur est accessible.');
            button.innerHTML = originalText;
            button.disabled = false;
        });
    }
}

// Fonction pour récupérer le token CSRF
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
