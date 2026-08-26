import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'daykin_backend.settings')
django.setup()

from datetime import date
from django.contrib.auth.models import User
from api.models import Celebrity, Article, Charity, LoveStory

# Celebrities
celebs = [
    dict(name='Michael Jackson', birthdate='Aug 29, 1958', birth_date=date(1958,8,29), profession='Singer · Dancer · Songwriter', nationality='🇺🇸 American', initials='MJ', gradient_from='#F5A623', gradient_to='#E91E8C', age=65, bio='Michael Jackson — The King of Pop who redefined music, fashion, and entertainment globally.'),
    dict(name='Rihanna', birthdate='Feb 20, 1988', birth_date=date(1988,2,20), profession='Singer · Entrepreneur', nationality='🇧🇧 Barbadian', initials='RI', gradient_from='#6C2BD9', gradient_to='#E91E8C', age=37, bio='Rihanna became one of the most influential artists of her generation, building a global empire in music and fashion.'),
    dict(name='Beyoncé', birthdate='Sep 4, 1981', birth_date=date(1981,9,4), profession='Singer · Actress · Producer', nationality='🇺🇸 American', initials='BK', gradient_from='#F5A623', gradient_to='#6C2BD9', age=43, bio='Beyoncé is widely regarded as one of the greatest entertainers of all time.'),
    dict(name='Cristiano Ronaldo', birthdate='Feb 5, 1985', birth_date=date(1985,2,5), profession='Football · Athlete', nationality='🇵🇹 Portuguese', initials='CR', gradient_from='#1DB954', gradient_to='#2BD97A', age=40, bio='Cristiano Ronaldo is considered one of the greatest footballers of all time.'),
    dict(name="Lupita Nyong'o", birthdate='Mar 1, 1983', birth_date=date(1983,3,1), profession='Actress · Director', nationality='🇰🇪 Kenyan', initials='LN', gradient_from='#E91E8C', gradient_to='#F5A623', age=42, bio='Lupita Nyongʼo is an award-winning Kenyan-Mexican actress.'),
    dict(name='Lionel Messi', birthdate='Jun 24, 1987', birth_date=date(1987,6,24), profession='Football · Athlete', nationality='🇦🇷 Argentine', initials='LM', gradient_from='#4FC3F7', gradient_to='#6C2BD9', age=37, bio='Lionel Messi is universally acclaimed as one of the greatest football players of all time.'),
]
for c in celebs:
    Celebrity.objects.get_or_create(name=c['name'], defaults=c)

admin = User.objects.get(username='admin')

# Articles
Article.objects.get_or_create(title='Champions League Final Preview', defaults=dict(content='Full preview of the champions league final...', category='sports', tag='Football', tag_color='purple', read_time='4 min read', reads=12400, author=admin, is_published=True))
Article.objects.get_or_create(title='Ronaldo Breaks All-Time Scoring Record', defaults=dict(content='Ronaldo has done it again...', category='sports', tag='Football', tag_color='purple', read_time='3 min read', reads=89000, author=admin, is_published=True))

# Charities
Charity.objects.get_or_create(title='Clean Water for Rural Uganda', defaults=dict(description='Bringing clean water to communities that need it most.', goal=5000, raised=3210, tag='Health', avatar='UG'))
Charity.objects.get_or_create(title='Girls Education Fund — East Africa', defaults=dict(description='Empowering girls through quality education.', goal=10000, raised=7890, tag='Education', avatar='GE'))
Charity.objects.get_or_create(title='Rebuilding After the Floods', defaults=dict(description='Helping flood-affected families rebuild their homes.', goal=8000, raised=2100, tag='Relief', avatar='FL'))

# Love Stories
LoveStory.objects.get_or_create(title='The Coffee Shop Encounter', defaults=dict(author=admin, author_name='Amara Diallo', excerpt='It started with a spilled latte and the most apologetic pair of brown eyes I had ever seen...', read_time='4 min read', likes=234, avatar='AD'))
LoveStory.objects.get_or_create(title='Across the Miles', defaults=dict(author=admin, author_name='Fatima Hassan', excerpt='Long distance they said was impossible. We said we\'d prove them wrong.', read_time='6 min read', likes=412, avatar='FH'))
LoveStory.objects.get_or_create(title='The Wrong Number', defaults=dict(author=admin, author_name='Grace Otieno', excerpt='I meant to call my sister. Instead I called a stranger who made me laugh for two hours straight.', read_time='3 min read', likes=189, avatar='GO'))

print("✅ Seed data loaded successfully!")
