def get_db_user_by_telegram_effective_user(telegram_user):
    from user_package.models import User

    user, created = User.objects.get_or_create(telegram_id=telegram_user.id)
    if created:
        user.full_name = telegram_user.full_name
        user.username = telegram_user.username
        user.save()

    return user


def create_user_package(user, dict_params):
    user.packages.create(**dict_params)


def get_user_packages_slug_list(user):
    packages = user.packages.values_list('slug', flat=True)
    return list(packages)


def get_users_that_follow_package(slug):
    from user_package.models import Package

    packages = Package.objects.filter(slug=slug)
    users = []
    for package in packages:
        if package.user not in users:
            users.append(package.user)

    return users


def update_package_version(slug, actual_version):
    from user_package.models import Package

    packages = Package.objects.filter(slug=slug)
    packages.update(last_check_version=actual_version)


def delete_user_package_by_slug(user, slug):
    user.packages.filter(slug=slug).delete()


def distinct_packages():
    from user_package.models import Package

    packages = Package.objects.all().distinct()
    return list(packages)
