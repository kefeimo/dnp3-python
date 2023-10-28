# current version in the setup.py file
current_version=$(sed -n -e 's/^.*__version__ = //p' setup.py)
current_version=$(echo ${current_version} | sed -e "s/'//g")

# current_tag is the last tagged relese in the repository.   From there
# we need to remove the v from the begining of the tag.
if ! $(git tag -l "v*" = ''); then
  # uses -V which is version sort to keep it monotonically increasing.
  current_tag=$(git tag -l "v*" | grep --invert-match '-' | sort --reverse -V  | sed -n 1p)
else
  current_tag=v$current_version
fi
current_tag=${current_tag#?}

new_version=$(python .github/workflows/versions.py ${current_tag} --prerelease)

new_tag=v${new_version}

sed -i "s/^.*-__version__ = /__version__ = $new_version/" setup.py

echo "New version is: ${new_version}"

# Finally because we want to be able to use the variable in later
# steps we set a NEW_TAG environmental variable
echo "NEW_TAG=$(echo ${new_tag})" >> $GITHUB_ENV