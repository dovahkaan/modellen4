document.addEventListener('DOMContentLoaded', () => {
    const githubButton = document.getElementById('github-login');
    if (!githubButton) {
        return;
    }

    githubButton.addEventListener('click', () => {
        const clientId = githubButton.dataset.clientId;
        const redirectUri = githubButton.dataset.redirectUri;
        const state = githubButton.dataset.state;
        if (!clientId) {
            alert('GitHub login is not configured yet. Please contact the administrator.');
            return;
        }
        const authorizeUrl = new URL('https://github.com/login/oauth/authorize');
        authorizeUrl.searchParams.set('client_id', clientId);
        if (redirectUri) {
            authorizeUrl.searchParams.set('redirect_uri', redirectUri);
        }
        if (state) {
            authorizeUrl.searchParams.set('state', state);
        }
        authorizeUrl.searchParams.set('scope', 'read:user user:email');
        authorizeUrl.searchParams.set('allow_signup', 'true');
        window.location.href = authorizeUrl.toString();
    });
});
