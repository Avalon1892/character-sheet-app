"""Verified base Marvelous Item pricing; no catalog or persistence side effects.

Complexity is an already-resolved talent-based value, not a talent count.
Source: https://spheresofpower.wikidot.com/magical-items
"""
from dataclasses import dataclass, replace
from fractions import Fraction
from collections import Counter

from app.crafting_rules import CraftingQuote


@dataclass(frozen=True)
class MarvelousItemPrice:
    market_price_gp: Fraction
    save_dc: int
    daily_uses: int | None
    total_uses: int | None


@dataclass(frozen=True)
class MarvelousRequirements:
    blockers: tuple[str, ...]
    bypassed: tuple[str, ...]
    dc_increase: int

    @property
    def eligible(self):
        return not self.blockers


def marvelous_aura_strength(caster_level):
    """PF1e magic-item aura bands (Detect Magic), not spell-level aura bands."""
    if isinstance(caster_level, bool) or not isinstance(caster_level, int) or caster_level < 1:
        raise ValueError('Item caster level must be a positive integer.')
    return 'Faint' if caster_level <= 5 else 'Moderate' if caster_level <= 11 else 'Strong' if caster_level <= 20 else 'Overwhelming'


def marvelous_requirements(*, caster_level, sphere_levels, feats, required_spheres,
                            required_talents=(), available_talents=(),
                            advanced_talents=(), protected_requirements=(),
                            available_requirements=(), prohibited_abilities=()):
    """Evaluate explicitly supplied crafting access, independently of Qt.

    Sphere levels must exclude temporary bonuses. Cooperative sources must be
    available for the entire construction period. Advanced talents and protected
    class requirements are never waived. Versatile Crafter can waive base spheres
    and each missing caster level, but not a tradition's prohibited abilities.
    """
    if isinstance(caster_level, bool) or not isinstance(caster_level, int) or caster_level < 1:
        raise ValueError("Item caster level must be a positive integer.")
    levels = {name.casefold(): value for name, value in sphere_levels.items()}
    if any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in levels.values()):
        raise ValueError("Permanent sphere levels must be nonnegative integers.")
    known_feats = {name.casefold() for name in feats}
    known_talents = {name.casefold() for name in available_talents}
    advanced = {name.casefold() for name in advanced_talents}
    requirements = {name.casefold() for name in available_requirements}
    versatile = "versatile crafter" in known_feats
    blockers, bypassed = [], []
    dc_increase = 0
    if not known_feats.intersection({"craft marvelous item", "craft wondrous item"}):
        blockers.append("Requires Craft Marvelous Item (or Craft Wondrous Item).")
    spheres = {name.casefold(): name for name in required_spheres}
    if not spheres or any(not name.strip() for name in spheres):
        raise ValueError("At least one base sphere is required.")
    for sphere in spheres.values():
        level = levels.get(sphere.casefold(), 0)
        if level == 0:
            message = f"Missing base sphere: {sphere}"
            (bypassed if versatile else blockers).append(message)
            if versatile:
                dc_increase += 5
        deficit = max(0, caster_level - level)
        if deficit:
            message = f"{sphere}: permanent caster level {level}, requires {caster_level}"
            (bypassed if versatile else blockers).append(message)
            if versatile:
                dc_increase += 5 * deficit
    for talent in {name.casefold(): name for name in required_talents}.values():
        if talent.casefold() in known_talents:
            continue
        message = f"Missing talent: {talent}"
        if talent.casefold() in advanced:
            blockers.append(message)
        else:
            bypassed.append(message)
            dc_increase += 5
    blockers.extend(f"Missing required feature: {name}" for name in protected_requirements
                    if name.casefold() not in requirements)
    blockers.extend(f"Casting tradition prohibits: {name}" for name in prohibited_abilities)
    return MarvelousRequirements(tuple(blockers), tuple(bypassed), dc_increase)


def marvelous_item_price(caster_level: int, complexity: int | Fraction, *, daily_uses: int = 1,
                         limited_uses: bool = False) -> MarvelousItemPrice:
    """Price the base effect, excluding optional traditions and costly components.

    Five daily uses means unlimited use; limited-use construction instead grants
    fifty total activations. Neither mode implies free spell-point resources.
    """
    for label, value in (("Caster level", caster_level), ("Daily uses", daily_uses)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{label} must be a positive integer.")
    if isinstance(complexity, bool) or not isinstance(complexity, (int, Fraction)) or complexity < 1:
        raise ValueError("Complexity must be an exact value of at least one.")
    if complexity > caster_level:
        raise ValueError("Item caster level must be at least its complexity.")
    if daily_uses > 5:
        raise ValueError("Use five daily uses for unlimited activation.")
    if limited_uses and daily_uses != 1:
        raise ValueError("Limited-total and daily-use construction cannot be combined.")
    base = Fraction(400 * caster_level * complexity)
    return MarvelousItemPrice(
        base * Fraction(5, 2) if limited_uses else base * daily_uses,
        10 + caster_level // 2,
        None if limited_uses or daily_uses == 5 else daily_uses,
        50 if limited_uses else None,
    )


# Imported subsections are retained for saved-data compatibility, but are not
# independently learnable item effects.
MARVELOUS_SUBSECTION_KEYS = frozenset({
    'divination:advanced-talent:divine-chart',
    'divination:advanced-talent:lay-of-the-land',
    'divination:advanced-talent:pathfinder',
    'fallen-fey:fey-blessing-talent:grimalkin-shade',
})

# Reviewed construction prerequisites use catalog identities, never prose parsing.
ADVANCED_CONSTRUCTION_REQUIREMENTS = {
    'divination:advanced-talent:speak-and-i-listen-dbh': (10, ('divination:advanced-talent:hear-name-sense-utility-dbh',)),
    'divination:advanced-talent:alternate-divinations-advanced-sense-origin': (1, ()),
    'divination:advanced-talent:arc-of-change-utility-sm': (0, ()),
    'divination:advanced-talent:sense-observation-sense-alienist-hb': (0, ('divination:sense-talent:detect-scrying-sense',)),
    'fallen-fey:advanced-talent:banish-to-faerie': (8, ()),
    'fallen-fey:advanced-talent:blinding-beauty-fey-blessing': (10, ()),
    'fallen-fey:advanced-talent:bound-to-nature-fey-blessing': (10, ()),
    'fallen-fey:advanced-talent:drowning-kiss-fey-blessing': (10, ()),
    'fallen-fey:advanced-talent:fairy-ring-traveler-utility': (5, ()),
    'fallen-fey:advanced-talent:fey-initiation': (15, ('fallen-fey:talent:greater-fey-link',)),
    'fallen-fey:advanced-talent:fey-invisibility-fey-blessing': (5, ('fallen-fey:fey-blessing-talent:fade-fey-blessing',)),
    'fallen-fey:advanced-talent:steal-skin-fey-blessing': (5, ()),
    'blood:advanced-talent:cardiovascular-ascension-quicken-still-crimdan': (10, ('blood:quicken-still-talent:cardiovascular-mastery-quicken-still-crimdan',)),
    'blood:advanced-talent:drain-lifeblood': (1, ()),
    'blood:advanced-talent:overclock': (18, ('blood:quicken-still-talent:control-oxygenation-quicken-still',)),
    'blood:advanced-talent:puppet-master': (10, ('blood:quicken-still-talent:blood-puppet-quicken',)),
    'blood:advanced-talent:sanguine-minion': (5, ('blood:talent:extract-blood-construct', 'blood:talent:lengthened-control')),
    'blood:advanced-talent:sanguiphilia-bap': (7, ('blood:blood-art-talent:martyr-s-tithings-blood-art-bap',)),
    'blood:advanced-talent:union-of-blood-bap': (10, ()),
    'divination:advanced-talent:assurance-of-the-future-sm': (0, ('divination:divine-talent:divine-future-divine',)),
    'divination:advanced-talent:cartographer-s-divinations-divine-utility-rw-hb': (5, ()),
    'divination:advanced-talent:detect-patronage-utility-lg': (0, ('divination:divine-talent:detect-spellcaster-divine',)),
    'divination:advanced-talent:discern-location-divine-utility': (15, ('divination:divine-talent:dowsing-divine-utility', 'divination:talent:greater-divine-range')),
    'divination:advanced-talent:divine-identity-divine-utility': (1, ('divination:sense-talent:discern-individual-sense',)),
    'divination:advanced-talent:divine-knowledge-divine-utility': (10, ('divination:advanced-talent:read-omens-divine-utility',)),
    'divination:advanced-talent:expansive-vision': (10, ()),
    'divination:advanced-talent:eye-in-the-sky-3pp': (0, ('divination:divine-talent:viewing-divine-utility',)),
    'divination:advanced-talent:eyes-of-the-cabal-bap': (5, ('divination:sense-talent:prying-sight-sense-bap',)),
    'divination:advanced-talent:greater-scrying-divine-utility': (15, ('divination:talent:greater-divine-range', 'divination:advanced-talent:scrying-utility', 'divination:divine-talent:viewing-divine-utility')),
    'divination:advanced-talent:hear-name-sense-utility-dbh': (5, ()),
    'divination:advanced-talent:mechanical-counterintelligence-lg': (0, ('divination:sense-talent:detect-scrying-sense',)),
    'divination:advanced-talent:otherworldly-viewing-lg': (10, ('divination:talent:greater-divine-range', 'divination:divine-talent:viewing-divine-utility')),
    'divination:advanced-talent:penetrating-divination': (1, ()),
    'divination:advanced-talent:power-of-the-name-utility-dbh': (10, ('divination:advanced-talent:hear-name-sense-utility-dbh',)),
    'divination:advanced-talent:read-omens-divine-utility': (5, ()),
    'divination:advanced-talent:remote-casting-divine-alienist-hb': (5, ('divination:divine-talent:viewing-divine-utility',)),
    'divination:advanced-talent:scrying-utility': (10, ('divination:talent:greater-divine-range', 'divination:divine-talent:viewing-divine-utility')),
    'divination:advanced-talent:sensitive-divinations-eo3': (1, ()),
    'divination:advanced-talent:soulbroker-s-sight-utility-sm': (0, ('divination:divine-talent:divine-treasure-divine-utility-alienist-hb',)),
    'divination:advanced-talent:trapfinding-sense': (1, ('divination:sense-talent:see-hazard-sense',)),
    'divination:advanced-talent:true-perception-sense-origin': (10, ('divination:sense-talent:ghost-sight-sense', 'divination:sense-talent:unhooded-sight-sense')),
    'divination:advanced-talent:unobscured-vision-sense': (10, ('divination:sense-talent:ghost-sight-sense',)),
    'dark:advanced-talent:animated-shadow-shadow': (5, ('dark:blot-darkness-shadow-talent:shadow-lurk-shadow',)),
    'dark:advanced-talent:black-and-black-morality-blot-darkness-shadow': (10, ('dark:talent:gaze-into-the-abyss',)),
    'dark:advanced-talent:eternal-darkness': (10, ('dark:talent:lingering-darkness',)),
    'dark:advanced-talent:lightless-penumbra-shadow': (1, ('dark:blot-darkness-shadow-talent:shadowed-mien-shadow',)),
    'dark:advanced-talent:melt-into-shadow': (10, ('dark:advanced-talent:animated-shadow-shadow',
        'dark:talent:flowing-darkness', 'dark:blot-darkness-shadow-talent:shadow-lurk-shadow')),
    'dark:advanced-talent:midnight-darkness': (10, ('dark:talent:greater-darkness',)),
    'dark:advanced-talent:one-with-the-void': (10, ('dark:meld-talent:step-through-darkness-meld',)),
    'dark:advanced-talent:pitch-black': (10, ('dark:blot-darkness-shadow-talent:pure-darkness-darkness',)),
    'dark:advanced-talent:shadow-double-shadow': (15, ('dark:advanced-talent:animated-shadow-shadow',
        'dark:blot-darkness-shadow-talent:shadow-lurk-shadow')),
    'dark:advanced-talent:shadow-walker-meld': (10, ('dark:meld-talent:step-through-darkness-meld',)),
    'dark:advanced-talent:vanish-in-shadow': (5, ('dark:meld-talent:hide-in-darkness-meld',)),
    'creation:advanced-talent:corp-criadhach-dbh': (10, ('creation:advanced-talent:duplicate', 'creation:advanced-talent:fleshcraft-material')),
    'creation:advanced-talent:costly-creation': (15, ('creation:material-talent:expanded-materials-material', 'creation:talent:lengthened-creation')),
    'creation:advanced-talent:create-minds-think-alike-jester-s-hb': (5, ('creation:talent:exquisite-detail-utility', 'enhancement:enhance-talent:bestow-intelligence-enhance')),
    'creation:advanced-talent:fleshcraft-material': (10, ()),
    'creation:advanced-talent:material-body-alter': (5, ('creation:alter-talent:change-material-alter',)),
    'creation:advanced-talent:mythical-material-maker-material': (15, ()),
    'creation:advanced-talent:imperfect-recreation-alienist-hb': (15, (
        'creation:advanced-talent:duplicate', 'creation:talent:exquisite-detail-utility',
        'creation:advanced-talent:fleshcraft-material', 'enhancement:enhance-talent:animate-object-enhance',
        'enhancement:enhance-talent:bestow-intelligence-enhance', 'enhancement:advanced-talent:bestow-life')),
    'creation:advanced-talent:create-materials': (10, ('creation:talent:lengthened-creation',)),
    'creation:advanced-talent:duplicate': (5, ('creation:talent:exquisite-detail-utility',)),
    'creation:advanced-talent:fabricate': (10, ('creation:alter-talent:forge-alter',)),
    'creation:advanced-talent:dissolution-alter': (0, ('creation:talent:potent-alteration',)),
    'creation:advanced-talent:integrate-item-alter-sm': (5, ('creation:talent:potent-alteration',)),
    'creation:advanced-talent:internal-creation-apoc': (0, ('creation:talent:distant-creation-range', 'creation:talent:potent-alteration')),
    'creation:advanced-talent:magma-mastery-material': (10, ('creation:material-talent:plasma-production-material',)),
    'creation:advanced-talent:ooze-originator-create': (5, ('creation:material-talent:acidic-creation-material',)),
    'creation:advanced-talent:permanent-change': (10, ('creation:alter-talent:change-material-alter',
        'creation:material-talent:expanded-materials-material', 'creation:alter-talent:forge-alter')),
    'creation:advanced-talent:plasma-projection': (5, ('creation:material-talent:plasma-production-material',)),
    'creation:advanced-talent:state-shift-alter': (10, ('creation:alter-talent:change-material-alter',)),
    'creation:advanced-talent:sustenance-material-utility': (1, ()),
    'time:advanced-talent:advanced-rewind': (10, ('time:talent:age-time',)),
    'time:advanced-talent:combo-breaker-sm': (0, ('time:talent:eject-time',)),
    'time:advanced-talent:divergent-retry-sm': (0, ('time:talent:retry-time',)),
    'time:advanced-talent:grey-hawk-s-gambit-3pp': (0, ('time:advanced-talent:shuffle-time-time-3pp',)),
    'time:advanced-talent:improved-eject-time': (17, ('time:talent:eject-time',)),
    'time:advanced-talent:interlocutor-across-time-lg': (10, ('time:advanced-talent:witness-across-time-lg',)),
    'time:advanced-talent:past-sight-utility': (5, ()),
    'time:advanced-talent:query-self-utility': (10, ()),
    'time:advanced-talent:reversion-utility': (10, ()),
    'time:advanced-talent:reversion-complete-utility': (15, ('time:advanced-talent:reversion-utility',)),
    'time:advanced-talent:temporal-haste': (9, ('time:talent:improved-haste',)),
    'time:advanced-talent:temporal-stasis': (15, ()),
    'time:advanced-talent:time-clone-time': (10, ()),
    'time:advanced-talent:shuffle-time-time-3pp': (0, ()),
    'time:advanced-talent:timeless-crane-s-hourglass-time-bth': (0, ()),
    'time:advanced-talent:witness-across-time-lg': (10, ()),
    'warp:advanced-talent:group-teleport': (10, ('warp:talent:mass-teleport-mass', 'warp:talent:ranged-warp-range')),
    'warp:advanced-talent:universal-teleport': (17, ('warp:talent:distant-teleport', 'warp:advanced-talent:flawless-teleport-utility',
        'warp:advanced-talent:true-teleport', 'warp:talent:unseeing-teleport')),
    'warp:advanced-talent:extradimensional-capacity-utility-apoc': (0, ('warp:space-talent:extradimensional-storage-space-utility',)),
    'destruction:advanced-talent:crystal-cocoon': (10, ()),
    'destruction:advanced-talent:radiation-blast-blast-type-fire-light': (5, ()),
    'destruction:advanced-talent:extreme-range': (5, ('destruction:talent:extended-range-range',) * 2),
    'destruction:advanced-talent:grandmaster-jester-s-hb': (0, ('destruction:blast-shape-talent:knight-s-blast-blast-shape-jester-s-hb',)),
    'protection:advanced-talent:pithing-protection-3pp': (10, ('protection:advanced-talent:spell-selectivity-dbh',
        'protection:aegis-ward-talent:spell-ward-aegis-ward')),
    'protection:advanced-talent:pithing-protection-arcforge-addendum-lg': (10, ()),
    'protection:advanced-talent:antimagic-aura-arcforge-addendum-lg': (10, ()),
    'protection:advanced-talent:spell-selectivity-arcforge-addendum-lg': (10, ()),
    'destruction:advanced-talent:adaptive-admixture-sm': (0, ('destruction:talent:admixture',)),
    'destruction:advanced-talent:conflagrant-cluster-3pp': (5, ()),
    'destruction:advanced-talent:disintegrate-blast-type': (5, ()),
    'destruction:advanced-talent:energy-cloud-blast-shape': (10, ()),
    'destruction:advanced-talent:greater-admixture': (5, ('destruction:talent:admixture',)),
    'destruction:advanced-talent:split-blast-alienist-hb': (0, ('destruction:talent:admixture', 'destruction:blast-shape-talent:blast-salvo-blast-shape-bap')),
    'destruction:advanced-talent:detonating-salvo-lg': (0, ('destruction:blast-shape-talent:blast-salvo-blast-shape-bap', 'destruction:blast-shape-talent:explosive-orb-blast-shape')),
    'destruction:advanced-talent:hounding-sphere-sm': (10, ('destruction:blast-shape-talent:energy-sphere-blast-shape',)),
    'destruction:advanced-talent:calamity-blast-shape': (10, ()),
    'protection:advanced-talent:permanent-ward': (10, ('protection:talent:enduring-protection',)),
    'protection:advanced-talent:planar-refuge-aegis-ward-rw-hb': (5, ()),
    'protection:advanced-talent:preserve-integrity-aegis-alienist-hb': (10, ()),
    'protection:advanced-talent:rapid-glyph-3pp': (0, ('protection:talent:glyph',)),
    'protection:advanced-talent:tripped-glyph-3pp': (0, ('protection:talent:glyph', 'protection:advanced-talent:rapid-glyph-3pp')),
    'protection:advanced-talent:stability-bottleneck-sm': (10, ('protection:aegis-ward-talent:spell-ward-aegis-ward',)),
    'protection:advanced-talent:voiding-suppression-3pp': (10, ('protection:aegis-ward-talent:spell-ward-aegis-ward',)),
    'protection:advanced-talent:spell-eater-aegis-3pp': (10, ('protection:succor-talent:negation-succor-3pp',)),
    'protection:advanced-talent:spell-selectivity-dbh': (10, ('protection:aegis-ward-talent:spell-ward-aegis-ward',)),
    'protection:advanced-talent:subtle-aegis': (5, ()),
    'protection:advanced-talent:true-protection': (10, ()),
    'protection:advanced-talent:undying-aegis': (7, ('protection:aegis-ward-talent:deathless-aegis',)),
    'protection:advanced-talent:unplottable-aegis': (15, ('protection:aegis-ward-talent:resistance-aegis',)),
    'protection:advanced-talent:adaptation-aegis': (10, ('protection:aegis-ward-talent:energy-resistance-aegis-ward',)),
    'protection:advanced-talent:antimagic-aura': (10, ('protection:aegis-ward-talent:spell-ward-aegis-ward',)),
    'protection:advanced-talent:automatic-fortification-3pp': (5, ('protection:talent:fortifier-3pp',)),
    'protection:advanced-talent:complex-glyph': (5, ('protection:talent:glyph',)),
    'protection:advanced-talent:improved-negation-3pp': (10, ('protection:succor-talent:negation-succor-3pp',)),
    'protection:advanced-talent:layered-glyph-3pp': (0, ('protection:talent:glyph',)),
    'protection:advanced-talent:mobile-ward-alienist-hb': (5, ()),
    'warp:advanced-talent:true-teleport': (10, ('warp:talent:distant-teleport', 'warp:talent:unseeing-teleport')),
    'warp:advanced-talent:dimensional-lock-space': (15, ('warp:space-talent:plane-manipulator-space',)),
    'warp:advanced-talent:create-demiplane-utility': (15, ('warp:space-talent:extradimensional-room-space',
        'creation:material-talent:expanded-materials-material')),
    'warp:advanced-talent:time-warp-jester-s-hb': (20, ('warp:talent:distant-teleport', 'warp:advanced-talent:true-teleport', 'warp:talent:unseeing-teleport')),
    'warp:advanced-talent:timeline-drift-lg': (10, ('warp:talent:distant-teleport', 'warp:talent:unseeing-teleport')),
    'warp:advanced-talent:dimensional-tracery-3pp': (0, ()),
    'warp:advanced-talent:planting-warp-3pp': (0, ('warp:talent:teleport-object', 'warp:talent:unwilling-teleport')),
    'warp:advanced-talent:store-structure': (1, ('warp:space-talent:extradimensional-storage-space-utility',)),
    'warp:advanced-talent:teleport-structure': (5, ('warp:talent:teleport-object',)),
    'warp:advanced-talent:warping-frenzy-lg': (5, ('warp:talent:pouncing-teleport', 'warp:talent:segmented-warp')),
    'warp:advanced-talent:brutalizing-shunt-apoc': (0, ()),
    'warp:advanced-talent:lethal-teleport-apoc': (5, ('warp:talent:unwilling-teleport',)),
    'warp:advanced-talent:portal-interstice-sm': (5, ('warp:space-talent:extradimensional-room-space',
        'warp:talent:mass-teleport-mass', 'warp:advanced-talent:portal', 'warp:space-talent:wormhole-space')),
    'warp:advanced-talent:portal-security-space-sm': (5, ()),
    'warp:advanced-talent:universal-teleport': (17, ('warp:talent:distant-teleport',
        'warp:advanced-talent:flawless-teleport-utility', 'warp:advanced-talent:true-teleport', 'warp:talent:unseeing-teleport')),
    'warp:advanced-talent:brain-preservation-alienist-hb': (15, ('warp:advanced-talent:organ-detachment-space-alienist-hb',)),
    'warp:advanced-talent:organ-detachment-space-alienist-hb': (10, ()),
    'warp:advanced-talent:randomized-planeshift-sm': (5, ('warp:talent:unseeing-teleport',)),
    'warp:advanced-talent:repel-the-unnatural-alienist-hb': (0, ('warp:space-talent:plane-manipulator-space',)),
    'warp:advanced-talent:warp-manipulator': (1, ('warp:space-talent:plane-manipulator-space', 'warp:talent:unwilling-teleport')),
    'warp:advanced-talent:manifest-planar-zone-space-dbh': (5, ()),
    'warp:advanced-talent:greater-planar-zone-sm': (5, ('warp:advanced-talent:manifest-planar-zone-space-dbh',)),
    'warp:advanced-talent:extradimensional-capacity-utility-apoc': (0, ('warp:space-talent:extradimensional-storage-space-utility',)),
    'warp:advanced-talent:extradimensional-torpor-space-apoc': (0, ('warp:space-talent:extradimensional-storage-space-utility',)),
    'warp:advanced-talent:flawless-teleport-utility': (15, ('warp:talent:distant-teleport',
        'warp:advanced-talent:true-teleport', 'warp:talent:unseeing-teleport')),
    'warp:advanced-talent:planeshift': (10, ('warp:talent:distant-teleport',
        'warp:advanced-talent:true-teleport', 'warp:talent:unseeing-teleport')),
    'warp:advanced-talent:portal': (5, ('warp:talent:mass-teleport-mass', 'warp:space-talent:wormhole-space')),
    'warp:advanced-talent:enduring-portal': (15, ('warp:talent:mass-teleport-mass', 'warp:advanced-talent:portal',
        'warp:space-talent:teleport-beacon-space', 'warp:talent:unwilling-teleport', 'warp:space-talent:wormhole-space')),
    'warp:advanced-talent:portal-network-dbh': (15, ('warp:advanced-talent:enduring-portal',
        'warp:talent:mass-teleport-mass', 'warp:advanced-talent:portal', 'warp:space-talent:teleport-beacon-space',
        'warp:talent:unwilling-teleport', 'warp:space-talent:wormhole-space')),
    'enhancement:advanced-talent:alternative-energy-jester-s-hb': (5, ('enhancement:enhance-talent:energy-enhancement-enhance',)),
    'enhancement:advanced-talent:antimagic-aegis': (1, ('enhancement:enhance-talent:magic-sink-enhance', 'protection:aegis-ward-talent:spell-ward-aegis-ward')),
    'enhancement:advanced-talent:ascetic-control': (5, ()),
    'enhancement:advanced-talent:bestow-life': (10, ('enhancement:enhance-talent:animate-object-enhance', 'enhancement:enhance-talent:bestow-intelligence-enhance')),
    'enhancement:advanced-talent:critical-climax-3pp': (5, ('enhancement:enhance-talent:deadly-weapon-enhance',)),
    'enhancement:advanced-talent:give-magic-life': (10, ('enhancement:enhance-talent:bestow-intelligence-enhance',)),
    'enhancement:advanced-talent:heart-of-hope-and-fear-sm': (0, ('enhancement:advanced-talent:normalize-enhance-sm', 'fate:advanced-talent:hold-on-hope-word-sm')),
    'fate:advanced-talent:hold-on-hope-word-sm': (0, ()),
    'enhancement:advanced-talent:inherent-enhancement-enhance-archmagi-s-hb': (17, ('enhancement:talent:deep-enhancement', 'enhancement:enhance-talent:mental-enhancement-enhance', 'enhancement:enhance-talent:physical-enhancement-enhance')),
    'enhancement:advanced-talent:normalize-enhance-sm': (0, ()),
    'enhancement:advanced-talent:referential-enhancements': (15, ('enhancement:talent:deep-enhancement', 'enhancement:talent:mass-enhancement-mass')),
    'enhancement:advanced-talent:reverse-gravity-enhance': (15, ('enhancement:enhance-talent:lighten-enhance',)),
    'enhancement:advanced-talent:vicious-accuracy-enhance-3pp': (5, ('enhancement:enhance-talent:deadly-weapon-enhance',)),
    'light:advanced-talent:daylight-light': (10, ()),
    'light:advanced-talent:diffuse-body': (7, ('light:talent:flicker-light',)),
    'light:advanced-talent:everglow': (1, ('light:talent:lingering-glow',)),
    'light:advanced-talent:incarnate-glow': (15, ('light:talent:flicker-light',)),
    'light:advanced-talent:light-speed': (15, ('light:talent:flicker-light', 'light:advanced-talent:incarnate-glow')),
    'light:advanced-talent:prismatic-radiance-light': (15, ('light:talent:searing-light-light', 'light:talent:style-utility')),
    'light:advanced-talent:radiation-light': (10, ('light:talent:irradiance-light',)),
    'light:advanced-talent:star-genesis': (10, ('light:talent:intensity-control',)),
    'telekinesis:advanced-talent:affix': (10, ('telekinesis:advanced-talent:effortless-telekinesis', 'telekinesis:talent:idle-concentration')),
    'telekinesis:advanced-talent:astral-affixation': (15, ('telekinesis:advanced-talent:affix', 'telekinesis:advanced-talent:effortless-telekinesis', 'telekinesis:talent:idle-concentration')),
    'telekinesis:advanced-talent:brutalizing-bludgeon-lg': (5, ('telekinesis:talent:telekinetic-maneuver',)),
    'telekinesis:advanced-talent:choking-grasp': (15, ('telekinesis:talent:telekinetic-crush',)),
    'telekinesis:advanced-talent:disperse-force': (10, ('telekinesis:talent:quick-reactions', 'telekinesis:talent:telekinetic-push')),
    'telekinesis:advanced-talent:effortless-telekinesis': (10, ()),
    'telekinesis:advanced-talent:focused-power': (5, ('telekinesis:talent:powerful-telekinesis',)),
    'telekinesis:advanced-talent:gravity-manipulation': (15, ('telekinesis:talent:gravity-shift',)),
    'telekinesis:advanced-talent:linear-acceleration': (10, ('telekinesis:talent:acceleration', 'telekinesis:talent:greater-speed')),
    'telekinesis:advanced-talent:puppet': (10, ('telekinesis:talent:finesse-utility', 'telekinesis:talent:telekinetic-maneuver')),
    'weather:advanced-talent:boiling-lord': (5, ()),
    'weather:advanced-talent:cacophonic-clap': (10, ('weather:talent:storm-lord',)),
    'weather:advanced-talent:climate': (10, ('weather:talent:greater-size-range',)),
    'weather:advanced-talent:climatic-shift': (15, ('weather:talent:lengthened-weather',)),
    'weather:advanced-talent:cold-lord': (1, ()),
    'weather:advanced-talent:desert-lord': (1, ()),
    'weather:advanced-talent:heat-lord': (1, ()),
    'weather:advanced-talent:rain-lord': (1, ()),
    'weather:advanced-talent:fire-tornadoes': (15, ('weather:advanced-talent:wind-lord',)),
    'weather:advanced-talent:volcano-lord': (10, ()),
    'weather:advanced-talent:wind-lord': (1, ()),
    'weather:advanced-talent:dehydration-pulse': (5, ('weather:advanced-talent:desert-lord',)),
    'weather:advanced-talent:rain-bomb': (1, ('weather:advanced-talent:rain-lord',)),
    'weather:advanced-talent:tornado-lord': (10, ('weather:advanced-talent:wind-lord',)),
    'weather:advanced-talent:radiation-lord-cata-hb': (10, ()),
    **{f'weather:advanced-talent:{suffix}': (10, ('weather:advanced-talent:radiation-lord-cata-hb',))
       for suffix in ('biohazard-cata-hb', 'contaminated-blows-mantle-radiation-cata-hb',
          'contamination-lord-cata-hb', 'interference-cloud-shroud-radiation-cata-hb',
          'melt-skin-shroud-radiation-cata-hb', 'radiotherapy-mantle-radiation-cata-hb')},
    'life:advanced-talent:feline-good-catgirl-hb': (5, ('life:talent:lingering-resilience',)),
    'life:advanced-talent:soul-consumption-dbh': (5, ('life:talent:revitalize', 'death:advanced-talent:create-soul-gem-dbh')),
    'death:advanced-talent:create-soul-gem-dbh': (5, ()),
    'life:advanced-talent:hypervitalize': (15, ('life:cure-talent:restore-health-cure', 'life:talent:revitalize')),
    'life:advanced-talent:make-whole': (10, ('life:talent:break-enchantment',
        'life:cure-talent:restore-senses-cure', 'life:cure-talent:restore-spirit-cure')),
    'life:advanced-talent:resurrection': (10, ('life:talent:resuscitate',)),
    'life:advanced-talent:resurrection-greater': (15, ('life:talent:break-enchantment',
        'life:advanced-talent:make-whole', 'life:cure-talent:restore-senses-cure',
        'life:cure-talent:restore-spirit-cure', 'life:advanced-talent:resurrection', 'life:talent:resuscitate')),
    'life:advanced-talent:resurrection-supreme-warden': (20, ('life:talent:break-enchantment',
        'life:advanced-talent:resurrection-greater', 'life:advanced-talent:make-whole',
        'life:cure-talent:restore-senses-cure', 'life:cure-talent:restore-spirit-cure',
        'life:advanced-talent:resurrection', 'life:talent:resuscitate')),
    'life:advanced-talent:transfiguration': (10, ('life:cure-talent:restore-health-cure',)),
    'life:advanced-talent:reincarnation-utility-3pp': (10, ('life:advanced-talent:resurrection', 'life:talent:resuscitate')),
    'life:advanced-talent:reincarnation-instant-3pp': (15, ('life:advanced-talent:reincarnation-utility-3pp',
        'life:advanced-talent:resurrection', 'life:talent:resuscitate')),
    'life:advanced-talent:reincarnation-manipulated-utility-3pp': (20, ('life:advanced-talent:reincarnation-utility-3pp',
        'life:advanced-talent:resurrection', 'life:talent:resuscitate')),
}

CROSS_SPHERE_CONSTRUCTION_REQUIREMENTS = {
    'divination:advanced-talent:arc-of-change-utility-sm': (('Time', None),),
    'divination:advanced-talent:soulbroker-s-sight-utility-sm': (('Fate', None),),
    'creation:advanced-talent:create-minds-think-alike-jester-s-hb': (('Enhancement', 'enhancement:enhance-talent:bestow-intelligence-enhance'),),
    'creation:advanced-talent:imperfect-recreation-alienist-hb': (
        ('Enhancement', 'enhancement:enhance-talent:animate-object-enhance'),
        ('Enhancement', 'enhancement:enhance-talent:bestow-intelligence-enhance'),
        ('Enhancement', 'enhancement:advanced-talent:bestow-life')),
    'enhancement:advanced-talent:antimagic-aegis': (('Protection', 'protection:aegis-ward-talent:spell-ward-aegis-ward'),),
    'enhancement:advanced-talent:heart-of-hope-and-fear-sm': (('Fate', 'fate:advanced-talent:hold-on-hope-word-sm'),),
    'weather:advanced-talent:fire-tornadoes': (('Nature', None),),
    'weather:advanced-talent:volcano-lord': (('Nature', None),),
    **{f'weather:advanced-talent:{suffix}': (('Destruction', None),)
       for suffix in ('radiation-lord-cata-hb', 'biohazard-cata-hb',
          'contaminated-blows-mantle-radiation-cata-hb', 'contamination-lord-cata-hb',
          'interference-cloud-shroud-radiation-cata-hb', 'melt-skin-shroud-radiation-cata-hb',
          'radiotherapy-mantle-radiation-cata-hb')},
    'life:advanced-talent:soul-consumption-dbh': (('Death', 'death:advanced-talent:create-soul-gem-dbh'),),
    'warp:advanced-talent:time-warp-jester-s-hb': (('Time', None),),
    'warp:advanced-talent:create-demiplane-utility': (('Creation', 'creation:material-talent:expanded-materials-material'),),
}

DIVINATION_SENSE_SPHERES = {
    'material sense': 'Creation', 'see in darkness': 'Dark', 'spirit sense': 'Death',
    'lifesense': 'Life', 'thoughtsense': 'Mind', 'unrestricted thoughtsense': 'Mind',
    'touchsight': 'Telekinesis', 'storm vision': 'Weather',
}


def cross_sphere_construction_requirements(contribution):
    """Fixed and selected-mode prerequisites, shared by eligibility and the card."""
    key = contribution.get('catalog_key')
    requirements = CROSS_SPHERE_CONSTRUCTION_REQUIREMENTS.get(key, ())
    if key == 'conjuration:form-talent:superior-senses-form':
        sphere = CONJURATION_SENSE_REQUIREMENTS.get(contribution.get('effect_choice'), (None, None))[0]
        if sphere: requirements += ((sphere, None),)
    if key == 'divination:advanced-talent:alternate-divinations-advanced-sense-origin':
        sphere = DIVINATION_SENSE_SPHERES.get(contribution.get('effect_choice'))
        if sphere: requirements += ((sphere, None),)
    if (key == 'divination:advanced-talent:speak-and-i-listen-dbh'
            and contribution.get('effect_choice') == 'teleport'):
        requirements += tuple(('Warp', 'warp:' + suffix) for suffix in (
            'talent:distant-teleport', 'talent:unseeing-teleport', 'advanced-talent:true-teleport'))
    return requirements

CONSTRUCTION_PACKAGE_REQUIREMENTS = {
    'weather:advanced-talent:fire-tornadoes': ('Nature (Fire package)',),
    'weather:advanced-talent:volcano-lord': ('Nature (Earth package)', 'Nature (Fire package)'),
}

CONJURATION_SENSE_REQUIREMENTS = {
    'see in darkness': ('Dark', None), 'lifesense': ('Life', None),
    'thoughtsense': ('Mind', None), 'touchsight': ('Telekinesis', None),
    'stone vision': ('Nature', 'Earth'), 'tremorsense': ('Nature', 'Earth'),
    'smoke vision': ('Nature', 'Fire'), 'scent metal': ('Nature', 'Metal'),
    'plant vision': ('Nature', 'Plant'), 'water vision': ('Nature', 'Water'),
}


def construction_package_requirements(contribution):
    """Fixed and selected-mode package access, independent of presentation."""
    key = contribution.get('catalog_key')
    required = CONSTRUCTION_PACKAGE_REQUIREMENTS.get(key, ())
    if key == 'conjuration:form-talent:superior-senses-form':
        package = CONJURATION_SENSE_REQUIREMENTS.get(contribution.get('effect_choice'), (None, None))[1]
        if package: required += (f'Nature ({package} package)',)
    return required

CREATION_MATERIAL_REQUIREMENTS = tuple('creation:' + suffix for suffix in (
    'material-talent:acidic-creation-material', 'material-talent:alchemical-creation-material',
    'material-talent:expanded-materials-material', 'material-talent:gaseous-generation-material',
    'material-talent:object-of-force-material', 'material-talent:plasma-production-material',
    'advanced-talent:fleshcraft-material', 'advanced-talent:magma-mastery-material',
    'advanced-talent:mythical-material-maker-material', 'advanced-talent:sustenance-material-utility'))

ALTERNATIVE_CONSTRUCTION_REQUIREMENTS = {
    **{'creation:advanced-talent:' + suffix: (tuple(key for key in CREATION_MATERIAL_REQUIREMENTS
        if key != 'creation:advanced-talent:' + suffix),) for suffix in (
            'fleshcraft-material', 'material-body-alter', 'mythical-material-maker-material')},
    'creation:advanced-talent:costly-creation': (('creation:advanced-talent:permanent-change', 'creation:advanced-talent:create-materials'),),
    'protection:advanced-talent:stability-bottleneck-sm': (('protection:advanced-talent:spell-selectivity-dbh', 'protection:advanced-talent:spell-selectivity-arcforge-addendum-lg'),),
    'protection:advanced-talent:voiding-suppression-3pp': (('protection:advanced-talent:spell-selectivity-dbh', 'protection:advanced-talent:spell-selectivity-arcforge-addendum-lg'),),
    'warp:advanced-talent:brutalizing-shunt-apoc': ((
        'warp:space-talent:create-gap-space', 'warp:talent:unseeing-teleport'),),
    'warp:advanced-talent:dimensional-tracery-3pp': ((
        'warp:space-talent:teleport-beacon-space', 'warp:space-talent:warp-link-space'),),
    'destruction:advanced-talent:crystal-cocoon': ((
        'destruction:blast-type-talent:crystal-blast-blast-type-crystal',
        'destruction:blast-type-talent:living-crystal-blast-blast-type-crystal'),),
    'protection:advanced-talent:pithing-protection-arcforge-addendum-lg': (
        ('protection:advanced-talent:spell-selectivity-dbh', 'protection:advanced-talent:spell-selectivity-arcforge-addendum-lg'),
        ('protection:aegis-ward-talent:spell-ward-aegis-ward', 'protection:aegis-ward-talent:technological-suppression-aegis-ward-lg')),
    'protection:advanced-talent:antimagic-aura-arcforge-addendum-lg': ((
        'protection:aegis-ward-talent:spell-ward-aegis-ward', 'protection:aegis-ward-talent:technological-suppression-aegis-ward-lg'),),
    'protection:advanced-talent:spell-selectivity-arcforge-addendum-lg': ((
        'protection:aegis-ward-talent:spell-ward-aegis-ward', 'protection:aegis-ward-talent:technological-suppression-aegis-ward-lg'),),
    'destruction:advanced-talent:calamity-blast-shape': ((
        'destruction:blast-shape-talent:explosive-orb-blast-shape', 'destruction:blast-shape-talent:sculpt-blast-blast-shape'),),
    'destruction:advanced-talent:blast-juggler-sm': ((
        'destruction:advanced-talent:energy-cloud-blast-shape', 'destruction:blast-shape-talent:energy-sphere-blast-shape'),),
    'destruction:advanced-talent:destructive-verticality-sm': ((
        'destruction:blast-shape-talent:energy-sphere-blast-shape', 'destruction:blast-shape-talent:explosive-orb-blast-shape',
        'destruction:blast-shape-talent:sculpt-blast-blast-shape'),),
}

COUNTED_ALTERNATIVE_CONSTRUCTION_REQUIREMENTS = {
    'destruction:advanced-talent:crystal-cocoon': (2, (
        'destruction:blast-type-talent:crystal-blast-blast-type-crystal',
        'destruction:blast-type-talent:living-crystal-blast-blast-type-crystal',
        'destruction:blast-type-talent:razor-blast-blast-type-crystal')),
    'destruction:advanced-talent:radiation-blast-blast-type-fire-light': (2, (
        'destruction:blast-type-talent:blistering-blast-blast-type-fire',
        'destruction:blast-type-talent:fire-blast-blast-type-fire',
        'destruction:blast-type-talent:searing-blast-blast-type-fire')),
}


def missing_construction_alternatives(contributions):
    keys = {row['catalog_key'] for row in contributions}
    applied = {row['catalog_key'] for row in contributions if not row.get('alternative')}
    missing = [(key, options) for key in sorted(keys)
                 if key in ALTERNATIVE_CONSTRUCTION_REQUIREMENTS
                 for options in ALTERNATIVE_CONSTRUCTION_REQUIREMENTS[key] if not applied.intersection(options)]
    for key in sorted(keys):
        if key not in COUNTED_ALTERNATIVE_CONSTRUCTION_REQUIREMENTS: continue
        count, options = COUNTED_ALTERNATIVE_CONSTRUCTION_REQUIREMENTS[key]
        if len(applied.intersection(options)) < count:
            missing.append((key, tuple(option for option in options if option not in applied)))
    return tuple(missing)


def mode_construction_prerequisites(contribution):
    """Explicit reviewed mode requirements, not prerequisite prose parsing."""
    from app.marvelous_base_powers import ABILITY_ENHANCEMENT_CHOICES, ENERGY_ENHANCEMENT_KEY, ALTERNATIVE_ENERGY_KEY
    if (contribution.get('catalog_key') == 'conjuration:form-talent:sanguine-creature-form'
            and contribution.get('effect_choice') == 'thirst'):
        return ('conjuration:form-talent:sanguine-creature-form',)
    if (contribution.get('catalog_key') == 'conjuration:talent:greater-summoning'
            and contribution.get('effect_choice') == '24 hours with Lingering Companion'):
        return ('conjuration:form-talent:lingering-companion-form',)
    if contribution.get('catalog_key') == 'divination:advanced-talent:speak-and-i-listen-dbh':
        if contribution.get('effect_choice') == 'scrying':
            return ('divination:advanced-talent:scrying-utility',)
        if contribution.get('effect_choice') == 'teleport':
            return tuple(key for _, key in cross_sphere_construction_requirements(contribution))
    if (contribution.get('catalog_key') == 'fallen-fey:fey-blessing-talent:fairy-dust-fey-blessing'
            and contribution.get('effect_choice') == 'flight'):
        return ('fallen-fey:fey-blessing-talent:fairy-flight-fey-blessing',)
    if (contribution.get('catalog_key') == 'fallen-fey:talent:bounty-of-the-fey-mass-3pp'
            and contribution.get('effect_choice') == 'shared blessing in an area'):
        return ('fallen-fey:talent:share-link',) * 2
    choices = ABILITY_ENHANCEMENT_CHOICES.get(contribution.get('catalog_key'), ())
    if contribution.get('effect_choice') in choices[3:]:
        return ('enhancement:talent:dual-enhancement',)
    if contribution.get('catalog_key') == ENERGY_ENHANCEMENT_KEY and contribution.get('effect_choice') in {'weapon: sonic', 'weapon: force'}:
        return (ALTERNATIVE_ENERGY_KEY,)
    if contribution.get('catalog_key') == 'creation:talent:precise-destruction-utility' and contribution.get('effect_choice') == 'magical trap':
        return ('creation:talent:potent-alteration',)
    if (contribution.get('catalog_key') == 'creation:advanced-talent:material-body-alter'
            and contribution.get('effect_choice') == 'hours per caster level with Lengthened Creation'):
        return ('creation:talent:lengthened-creation',)
    if (contribution.get('catalog_key') == 'creation:advanced-talent:duplicate'
            and contribution.get('effect_choice') == 'instantaneous object copy'):
        return ('creation:advanced-talent:create-materials',)
    return ()


def missing_required_construction_modes(contributions):
    """Reviewed prerequisite modes that must be integrated, not merely owned."""
    requirements = [('light:advanced-talent:radiation-light', 'light:talent:irradiance-light', 'nauseating bright light'),
        ('blood:advanced-talent:overclock', 'blood:quicken-still-talent:control-oxygenation-quicken-still', 'quicken with extra attacks')]
    for row in contributions:
        if (row['catalog_key'] == 'conjuration:form-talent:sanguine-creature-form'
                and row.get('effect_choice') == 'thirst'):
            requirements.append((row['catalog_key'], row['catalog_key'], 'blood drain'))
        if row['catalog_key'] == 'creation:advanced-talent:dissolution-alter':
            mode = {'unattended non-magical object': 'enhanced repair or destroy',
                'attended, magical or creature target': 'affect magical, attended or construct target'}.get(row.get('effect_choice'))
            if mode: requirements.append((row['catalog_key'], 'creation:talent:potent-alteration', mode))
        if row['catalog_key'] == 'telekinesis:advanced-talent:gravity-manipulation':
            mode = {'concentration (2 SP total)': 'concentration',
                    'Sustained Force (2 SP total)': 'Sustained Force'}.get(row.get('effect_choice'))
            if mode: requirements.append((row['catalog_key'], 'telekinesis:talent:gravity-shift', mode))
    return tuple(dict.fromkeys((owner, child, mode) for owner, child, mode in requirements
        if any(row['catalog_key'] == owner for row in contributions)
        and not any(row['catalog_key'] == child and row.get('effect_choice') == mode
                    and not row.get('alternative') for row in contributions)))


def missing_construction_prerequisites(contributions):
    """Reviewed transitive additions in deterministic dependency order."""
    owned = {row['catalog_key'] for row in contributions}
    seen, missing = Counter(row['catalog_key'] for row in contributions if not row.get('alternative')), []
    def visit(key):
        for required, count in Counter(ADVANCED_CONSTRUCTION_REQUIREMENTS.get(key, (0, ()))[1]).items():
            deficit = count - seen[required]
            if deficit <= 0: continue
            seen[required] = count
            visit(required); missing.extend([required] * deficit)
    for key in sorted(owned): visit(key)
    mode_counts = Counter()
    for row in contributions:
        mode_counts |= Counter(mode_construction_prerequisites(row))
    for required, count in sorted(mode_counts.items()):
        deficit = count - seen[required]
        if deficit > 0:
            seen[required] = count
            visit(required); missing.extend([required] * deficit)
    for owner, child, _ in missing_required_construction_modes(contributions):
        if owner != child or child in missing: continue
        # A self-key prerequisite needs a separate configured selection, not
        # replacement of the dependent talent's mode. New rows start blank.
        if not any(row['catalog_key'] == child and not row.get('effect_choice')
                   and not row.get('alternative') for row in contributions):
            missing.append(child)
    return tuple(missing)


def advanced_construction_blockers(contributions, caster_level, *, display_names=None):
    from app.marvelous_base_powers import TALENT_EFFECT_MINIMUM_CL
    keys = {row['catalog_key'] for row in contributions}
    applied_counts = Counter(row['catalog_key'] for row in contributions if not row.get('alternative'))
    blockers = []
    names = display_names or {}
    from itertools import combinations
    from app.marvelous_base_powers import CONJURATION_TYPE_KEYS, PLANAR_CREATURE_CHOICES
    type_rows = [row for row in contributions if row['catalog_key'] in CONJURATION_TYPE_KEYS]
    if any(left['catalog_key'] != right['catalog_key'] and contributions_can_coexist(left, right)
           for left, right in combinations(type_rows, 2)):
        blockers.append('A Conjuration companion may benefit from only one type talent at a time.')
    if any(all(contributions_can_coexist(left, right) for left, right in combinations(group, 2))
           for group in combinations(type_rows, 3)):
        blockers.append('A Conjuration type talent may be taken at most twice for the same companion.')
    planar = [row for row in type_rows if row['catalog_key'] == 'conjuration:type-talent:planar-creature-type'
              and row.get('effect_choice') in PLANAR_CREATURE_CHOICES]
    for left, right in combinations(planar, 2):
        if not contributions_can_coexist(left, right): continue
        first_group, first_benefits = left['effect_choice'].split(': ')
        second_group, second_benefits = right['effect_choice'].split(': ')
        if first_group != second_group or set(first_benefits.split(' + ')) & set(second_benefits.split(' + ')):
            blockers.append('Planar Creature: the second selection must grant the remaining two benefits of the same alignment.')
            break
    blockers.extend(f'{names.get(key, key)} is a rules subsection, not a separate talent; choose its parent talent and effect mode.'
                    for key in sorted(keys & MARVELOUS_SUBSECTION_KEYS))
    blockers.extend(f'{names.get(owner, owner)}: prerequisite {names.get(child, child)} must use {mode}.'
                    for owner, child, mode in missing_required_construction_modes(contributions))
    for row in contributions:
        for required, count in Counter(mode_construction_prerequisites(row)).items():
            if applied_counts[required] < count:
                blockers.append(f'{names.get(row["catalog_key"], row["catalog_key"])}: selected mode requires {count} fixed selection(s) of prerequisite talent {names.get(required, required)}.')
    for row in contributions:
        key, choice = row['catalog_key'], row.get('effect_choice', '')
        minimum = TALENT_EFFECT_MINIMUM_CL.get(key, {}).get(choice, 0)
        if caster_level < minimum:
            blockers.append(f'{names.get(key, key)} ({choice}): item caster level must be at least {minimum}.')
    blockers.extend(f'{names.get(key, key)}: include one prerequisite talent: '
                    + ' or '.join(names.get(option, option) for option in options) + '.'
                    for key, options in missing_construction_alternatives(contributions))
    if any(contributions_can_coexist(left, right)
           for left in contributions if left['catalog_key'] == 'protection:advanced-talent:mobile-ward-alienist-hb'
           for right in contributions if right['catalog_key'] == 'protection:advanced-talent:permanent-ward'):
        blockers.append('Mobile Ward cannot benefit from Permanent Ward in the same effect.')
    for left_key, right_key, message in (
        ('dark:advanced-talent:eternal-darkness', 'dark:talent:clinging-darkness', 'Eternal Darkness cannot be centered on a creature or object with Clinging Darkness.'),
        ('dark:advanced-talent:eternal-darkness', 'dark:talent:rolling-blackout', 'Eternal Darkness cannot be moved with Rolling Blackout.'),
        ('life:talent:affliction', 'life:talent:fount-of-life', 'Affliction cannot be combined with Fount of Life.'),
        ('life:talent:instill-life-instill', 'life:talent:empathic-healing', 'Instill Life cannot be augmented by Empathic Healing.'),
    ):
        if any(contributions_can_coexist(left, right)
               for left in contributions if left['catalog_key'] == left_key
               for right in contributions if right['catalog_key'] == right_key):
            blockers.append(message)
    for key in sorted(keys):
        requirement = ADVANCED_CONSTRUCTION_REQUIREMENTS.get(key)
        if requirement is None: continue
        minimum, required = requirement
        if caster_level < minimum:
            blockers.append(f'{names.get(key, key)}: item caster level must be at least {minimum}.')
        blockers.extend(f'{names.get(key, key)}: prerequisite talent must be included in this effect: {names.get(talent, talent)}'
                        + (f' (requires {count}, included {applied_counts[talent]})' if count > 1 else '') + '.'
                        for talent, count in Counter(required).items() if applied_counts[talent] < count)
    return tuple(blockers)


def contributions_can_coexist(left, right):
    """Only options in the same alternative group are mutually exclusive."""
    return not (left.get('alternative') and right.get('alternative')
                and left.get('alternative_group', 1) == right.get('alternative_group', 1))


REVIEWED_METAMAGIC_SP_COSTS = {'maximize spell': 3, 'empower spell': 2}


def feat_integration_defaults(name):
    points = REVIEWED_METAMAGIC_SP_COSTS.get(name.casefold())
    return dict(name=name, metamagic=points is not None, additional_spell_points=points or 0)


def feat_integration_complexity(integrations):
    """Explicit reviewed feat integration; metamagic adds its extra SP cost."""
    seen, total = set(), 0
    for feat in integrations:
        name = feat.get('name', '').strip()
        metamagic, points = feat.get('metamagic', False), feat.get('additional_spell_points', 0)
        if not name or name.casefold() in seen: raise ValueError('Integrated feats must have unique names.')
        if not isinstance(metamagic, bool) or isinstance(points, bool) or not isinstance(points, int) or points < 0:
            raise ValueError('Invalid metamagic integration cost.')
        if not metamagic and points: raise ValueError('Only metamagic feats add spell-point integration costs.')
        minimum = REVIEWED_METAMAGIC_SP_COSTS.get(name.casefold())
        if minimum is not None and (not metamagic or points < minimum):
            raise ValueError(f'{name} requires metamagic integration and at least {minimum} additional spell points.')
        seen.add(name.casefold()); total += 1 + points
    return total


def tradition_costs(base_price, *, cheap=False, expensive=False, other_reduction=Fraction(0)):
    """Reviewed material/resale adjustments, separate from base work pricing.

    Cheap reduces original materials by 10%, stacks additively with reductions,
    and floors materials at 40% of base price. Expensive changes materials only.
    Other reduction is a fraction of original material cost, not market value.
    """
    if not isinstance(cheap, bool) or not isinstance(expensive, bool) or (cheap and expensive):
        raise ValueError('Cheap and Expensive are mutually exclusive boolean options.')
    if isinstance(base_price, bool) or not isinstance(base_price, (int, Fraction)) or base_price <= 0:
        raise ValueError('Base price must be a positive exact value.')
    if isinstance(other_reduction, bool) or not isinstance(other_reduction, (int, Fraction)) or not 0 <= other_reduction <= 1:
        raise ValueError('Other reduction must be an exact fraction from zero to one.')
    base = Fraction(base_price)
    fraction = max(Fraction(4, 5), 1 - Fraction(1, 10) - other_reduction) if cheap else 1 - other_reduction
    materials = base / 2 * fraction * (Fraction(5, 4) if expensive else 1)
    return materials, base * fraction if cheap else base


def talent_construction_spell_points(entry, *, reviewed_only=False, base_power=None):
    """Reviewed mandatory default, not optional SP inferred from catalog prose.

    Ultimate Teleport Beacon spends one SP to place or use a beacon. These are
    separate activations, not two SP charged together. Basic Teleport comes
    from the Warp base power and is not another talent contribution.
    Ultimate basic teleport is free; True Teleport therefore adds two SP.
    Planeshift adds two, Portal adds one, and sustained Enduring Portal adds
    one beyond its integrated prerequisites. Optional variants remain explicit.
    """
    from app.marvelous_base_powers import DESTRUCTION_BLAST_TYPES, DESTRUCTION_BLAST_SHAPES, TALENT_EFFECT_SP_CHOICES, LIGHT_LENSES, LIFE_VITALITY_EFFECTS, CONJURATION_TYPE_KEYS, FATE_MOTIFS, FATE_IMMEDIATE_WORDS
    if entry.get('key') in FATE_IMMEDIATE_WORDS: return 1
    if entry.get('key') in FATE_MOTIFS:
        return 0 if base_power == 'fate:motif' else 1
    from app.marvelous_base_powers import DARK_MELDS
    if base_power == 'dark:meld' and entry.get('key') in DARK_MELDS: return 0
    if entry.get('key') in LIGHT_LENSES: return 0
    if entry.get('key') in LIFE_VITALITY_EFFECTS: return 0
    if choices := TALENT_EFFECT_SP_CHOICES.get(entry.get('key')):
        return min(choices.values())
    if entry.get('key') == 'destruction:blast-shape-talent:energy-sphere-blast-shape': return 0
    if entry.get('key') == 'destruction:blast-shape-talent:energy-wall-blast-shape': return 0
    if entry.get('key') == 'destruction:blast-shape-talent:explosive-orb-blast-shape': return 0
    if entry.get('key') == 'destruction:blast-shape-talent:blast-salvo-blast-shape-bap': return 0
    if profile := DESTRUCTION_BLAST_TYPES.get(entry.get('key')):
        return profile[3]
    if entry.get('key') in DESTRUCTION_BLAST_SHAPES: return 1
    return {
        'fate:word-talent:classify-word-utility': 1,
        'fate:word-talent:mercy-word-curse': 1,
        'fate:word-talent:subvert-weapon-word-curse': 1,
        'fate:word-talent:enmity-word-curse': 1,
        **{key: 0 for key in CONJURATION_TYPE_KEYS},
        **{'conjuration:form-talent:' + suffix: 0 for suffix in (
            'aligned-creature-form', 'altered-size-form', 'animal-creature-form', 'armored-companion-form',
            'avian-creature-form', 'battle-creature-form', 'bestial-form', 'boon-companion-form',
            'camouflaged-companion-form', 'capable-companion-form', 'climbing-companion-form',
            'crafting-creature-form', 'draconic-creature-form', 'earth-creature-form', 'elemental-creature-form',
            'explosive-companion-form', 'extra-limbs-form', 'extreme-situations-form',
            'fortified-companion-form', 'implement-bearer-form', 'infectious-creature-form',
            'magic-attacks-form', 'magic-vessel-form-alienist-hb', 'magical-companion-form',
            'monstrous-attacks-form', 'mount-form', 'muensterous-companion-form-jester-s-hb',
            'mystical-companion-form', 'natural-aspect-form', 'powerful-companion-form',
            'quick-companion-form', 'raging-companion-form', 'ravenous-creature-form',
            'resistant-creature-form', 'roguish-creature-form', 'sage-companion-form',
            'sanguine-creature-form', 'shadow-creature-form', 'shield-bearer-form', 'shocking-creature-form',
            'skill-mimic-form-utility-dbh', 'skillful-companion-form-utility',
            'spell-warded-companion-form', 'stinking-companion-form', 'thorned-companion-form',
            'trade-expertise-form-lots', 'transformative-form-utility', 'trapbreaking-companion-form',
            'water-being-form', 'web-spinner-form', 'willful-companion-form')},
        # The item-specific duration steps replace these talents' ordinary SP costs.
        'conjuration:form-talent:lingering-companion-form': 0,
        # Simple blessings spend their one activation SP and have no separately
        # paid action in these modes: +1 talent +1 SP matches the item rule's +2.
        # Blessings with additional paid subabilities remain separately reviewed.
        **{'fallen-fey:fey-blessing-talent:' + suffix: 1 for suffix in (
            'animate-hair-fey-blessing', 'beckoning-call-fey-blessing-utility',
            'crown-of-the-courts-fey-blessing', 'enchanting-music-fey-blessing',
            'fae-light-fey-blessing-utility', 'fairy-flight-fey-blessing',
            'feline-omens-fey-blessing-catgirl-hb', 'fey-beauty-fey-blessing-utility',
            'fey-potency-fey-blessing', 'fey-secrets-fey-blessing',
            'gremlin-s-presence-fey-blessing', 'listen-to-the-wind-fey-blessing-utility',
            'long-step-fey-blessing', 'mantle-of-autumn-fey-blessing', 'misplacement-fey-blessing',
            'natural-blessing-fey-blessing', 'natural-dominion-fey-blessing',
            'nature-s-empathy-fey-blessing-utility', 'plant-friend-fey-blessing',
            'saboteur-fey-blessing-utility', 'snare-setter-fey-blessing',
            'stunning-glance-fey-blessing', 'tree-meld-fey-blessing', 'trickery-fey-blessing',
            'unseelie-aura-fey-blessing', 'unthreatening-form-fey-blessing',
            'water-creature-fey-blessing', 'weapons-of-the-wild-fey-blessing',
            'wild-walk-fey-blessing', 'winterfey-fey-blessing')},
        # Detect Scrying already contributes the one SP of Sense Observation.
        'divination:advanced-talent:sense-observation-sense-alienist-hb': 0,
        # Cost of the spell/effect cast through the sensor is separate.
        'divination:advanced-talent:remote-casting-divine-alienist-hb': 1,
        'fallen-fey:talent:feytouch-strike-strike-3pp': 0,
        'blood:quicken-still-talent:blood-puppet-quicken': 1,
        'blood:quicken-still-talent:manipulate-alchemy-quicken-still': 0,
        'blood:blood-art-talent:gory-armaments-blood-art-bap': 0,
        'blood:advanced-talent:drain-lifeblood': 1,
        'blood:advanced-talent:essence-manipulation-bap': 0,
        'blood:advanced-talent:overclock': 3,
        'blood:advanced-talent:puppet-master': 0,
        'blood:advanced-talent:sanguine-minion': 2,
        'blood:advanced-talent:sanguiphilia-bap': 0,
        'blood:advanced-talent:union-of-blood-bap': 3,
        **{'blood:talent:' + suffix: 0 for suffix in (
            'blood-tracking', 'complex-control-apoc', 'exsanguinating-strike-strike-bap',
            'hemorrhage', 'improved-bleed', 'inject-crimdan', 'lengthened-control',
            'lingering-control', 'mana-bleed', 'ranged-blood-magic-range-bap', 'self-control')},
        'blood:talent:hemo-goblin-jester-s-hb': 1,
        'blood:talent:mass-blood-magic-mass-bap': 1,
        **{'divination:advanced-talent:' + suffix: 0 for suffix in (
            'assurance-of-the-future-sm', 'detect-patronage-utility-lg', 'divine-identity-divine-utility',
            'eye-in-the-sky-3pp', 'mechanical-counterintelligence-lg', 'otherworldly-viewing-lg',
            'penetrating-divination', 'power-of-the-name-utility-dbh', 'sensitive-divinations-eo3',
            'soulbroker-s-sight-utility-sm')},
        'divination:advanced-talent:hear-name-sense-utility-dbh': 1,
        'divination:advanced-talent:trapfinding-sense': 0,  # See Hazard already supplies 1 SP.
        'divination:advanced-talent:read-omens-divine-utility': 2,
        'divination:advanced-talent:true-perception-sense-origin': 0,  # Ghost Sight + Unhooded Sight: 2 SP.
        'divination:advanced-talent:unobscured-vision-sense': 2,  # Plus Ghost Sight: 3 SP.
        # These replace prerequisite effects' costs; their integrated rows
        # already supply Dowsing (1), Read Omens (2), and Viewing (1).
        'divination:advanced-talent:discern-location-divine-utility': 2,
        'divination:advanced-talent:divine-knowledge-divine-utility': 1,
        'divination:advanced-talent:scrying-utility': 1,
        **{'divination:sense-talent:' + suffix: 1 for suffix in (
            'battlefield-sense-sense', 'detect-scrying-sense', 'discern-individual-sense',
            'foreshadow-sense', 'ghost-sight-sense', 'nature-sense-sense', 'prescience-sense',
            'prying-sight-sense-bap', 'see-hazard-sense', 'sense-presence-sense-alienist-hb',
            'sniper-s-eye-sense', 'tremorsense-sense', 'unhooded-sight-sense')},
        **{'divination:sense-talent:' + suffix: 2 for suffix in (
            'sense-magic-sense', 'shared-perception-sense')},
        **{'divination:divine-talent:' + suffix: 1 for suffix in (
            'augury-divine-utility', 'detect-secrets-divine-utility', 'detect-spellcaster-divine',
            'divine-information-divine-utility', 'dowsing-divine-utility', 'sensory-overload-divine',
            'viewing-divine-utility', 'witness-the-city-divine-utility')},
        **{'divination:divine-talent:' + suffix: 0 for suffix in (
            'divine-biohazard-divine-alienist-hb', 'divine-capability-divine-utility-sm',
            'divine-future-divine', 'divine-relationships-divine-utility-3pp',
            'divine-treasure-divine-utility-alienist-hb')},
        **{'divination:talent:' + suffix: 0 for suffix in (
            'expanded-divinations', 'fast-divinations', 'greater-divine-range', 'lingering-divination')},
        **{'dark:blot-darkness-shadow-talent:' + suffix: 0 for suffix in (
            'black-lung-darkness', 'directional-darkness-darkness', 'disorienting-darkness-darkness',
            'edge-of-night-darkness-jester-s-hb', 'fearful-darkness-blot-darkness', 'flat-black-blot',
            'hungry-darkness-blot-darkness', 'intoxicating-darkness-blot-darkness',
            'looming-darkness-blot-darkness', 'numbing-darkness-blot-darkness',
            'shadow-slick-blot-shadow', 'shadow-tag-blot-darkness-shadow', 'tenebrous-legerdemain-blot-darkness')},
        **{'dark:blot-darkness-shadow-talent:' + suffix: 1 for suffix in (
            'creeping-lethargy-blot-darkness', 'obscure-passage-blot', 'shadow-lurk-shadow',
            'silent-darkness-darkness', 'snagging-darkness-blot', 'stygian-immersion-blot', 'thick-darkness-darkness')},
        'dark:advanced-talent:black-and-black-morality-blot-darkness-shadow': 2,
        'dark:advanced-talent:midnight-darkness': 2,
        'dark:advanced-talent:lightless-penumbra-shadow': 1,
        'dark:blot-darkness-shadow-talent:pure-darkness-darkness': 0,
        'dark:meld-talent:hide-in-darkness-meld': 1,
        **{'dark:talent:' + suffix: 0 for suffix in (
            'insinuate', 'rolling-blackout', 'shadow-coterie', 'shifting-shadows',
            'instill-dark-instill', 'shadow-strike-strike-3pp',
            'clinging-darkness', 'dampen-light', 'dappled-shadows', 'extinguish', 'flowing-darkness',
            'gaze-into-the-abyss', 'greater-darkvision', 'greater-meld', 'lingering-darkness',
            'obfuscation', 'quick-meld', 'ranged-darkness-range', 'wall-of-darkness')},
        **{'dark:talent:' + suffix: 1 for suffix in ('dual-darkness', 'greater-darkness', 'mass-meld-mass',
            'sinister-surprise', 'umbral-burst')},
        'life:talent:break-enchantment': 1,
        'telekinesis:advanced-talent:affix': 2,
        'telekinesis:advanced-talent:astral-affixation': 1,
        'telekinesis:advanced-talent:choking-grasp': 2,
        # Disperse Force's two-SP total includes the integrated Quick Reactions SP.
        'telekinesis:advanced-talent:disperse-force': 1,
        'telekinesis:advanced-talent:linear-acceleration': 2,
        'telekinesis:advanced-talent:puppet': 1,
        'telekinesis:talent:quick-reactions': 1,
        **{f'telekinesis:talent:{suffix}': 1 for suffix in ('homing', 'kinetic-field', 'pantomime-cage-jester-s-hb')},
        **{f'telekinesis:talent:{suffix}': 0 for suffix in (
            'dampening-field', 'dancing-weapon', 'excessive-force-bap', 'flight', 'floating-shield',
            'forceful-telekinesis', 'increased-range-range', 'mobile-bludgeon', 'orbit', 'parry',
            'return', 'seizing-strike-strike-3pp', 'steal', 'sweeping-bludgeons-bap',
            'telekinetic-tools', 'whirlwind-assembly')},
        **{f'telekinesis:{suffix}': 0 for suffix in (
            'advanced-talent:brutalizing-bludgeon-lg', 'advanced-talent:effortless-telekinesis',
            'talent:acceleration', 'talent:greater-speed', 'talent:idle-concentration',
            'talent:powerful-telekinesis', 'talent:finesse-utility', 'talent:telekinetic-crush',
            'talent:telekinetic-maneuver')},
        'light:advanced-talent:daylight-light': 2,
        'light:advanced-talent:everglow': 1,
        'light:advanced-talent:incarnate-glow': 2,
        'light:advanced-talent:prismatic-radiance-light': 3,
        # Irradiance's paid nausea mode contributes the other one SP.
        'light:advanced-talent:radiation-light': 1,
        **{f'light:talent:{suffix}': 1 for suffix in (
            'area-glow', 'bound-light-light', 'dual-light', 'encompassing-light-light',
            'hypnotic-pattern-light', 'instill-glow-instill', 'mass-lens-mass',
            'precious-light', 'repelling-light-light', 'revealing-light-light', 'visual-overload-light')},
        **{f'light:talent:{suffix}': 0 for suffix in (
            'bend-radiance', 'black-light', 'dancing-lights', 'fenestrate-light', 'flare',
            'glory', 'guiding-light-light', 'inner-sun-light', 'light-link', 'lure-light-light',
            'ranged-light-range', 'revelation-light', 'shining-arsenal-light', 'solar-strike-strike',
            'sunstroke-light')},
        **{f'light:nimbus-talent:{suffix}': 0 for suffix in ('beam-nimbus', 'trail-nimbus', 'weird-radiance-nimbus')},
        **{f'light:{suffix}': 0 for suffix in (
            'advanced-talent:diffuse-body', 'advanced-talent:light-speed',
            'talent:flicker-light', 'talent:lingering-glow', 'talent:searing-light-light',
            'talent:style-utility', 'talent:intensity-control')},
        'enhancement:enhance-talent:animate-object-enhance': 1,
        'enhancement:enhance-talent:bestow-intelligence-enhance': 1,
        'enhancement:enhance-talent:lighten-enhance': 1,
        'enhancement:talent:mass-enhancement-mass': 1,
        'enhancement:talent:dual-enhancement': 1,
        'enhancement:talent:flash-of-excellence-sm': 1,
        'enhancement:talent:power-parasitism-alienist-hb': 1,
        'enhancement:talent:ranged-enhancement-range': 0,
        'enhancement:enhance-talent:steal-capacity-enhance': 1,
        'enhancement:enhance-talent:steal-senses-enhance': 1,
        'enhancement:advanced-talent:antimagic-aegis': 1,
        'enhancement:advanced-talent:ascetic-control': 2,
        # Bestow Life's three-SP total includes both one-SP prerequisites.
        'enhancement:advanced-talent:bestow-life': 1,
        'enhancement:advanced-talent:heart-of-hope-and-fear-sm': 1,
        'enhancement:advanced-talent:referential-enhancements': 2,
        **{f'enhancement:{suffix}': 0 for suffix in (
            'advanced-talent:alternative-energy-jester-s-hb', 'advanced-talent:critical-climax-3pp',
            'advanced-talent:normalize-enhance-sm', 'advanced-talent:vicious-accuracy-enhance-3pp',
            'enhance-talent:magic-sink-enhance', 'enhance-talent:deadly-weapon-enhance',
            'enhance-talent:energy-enhancement-enhance', 'talent:deep-enhancement',
            'enhance-talent:alter-movement-enhance', 'enhance-talent:cripple-enhance',
            'enhance-talent:emphasize-belief-enhance', 'enhance-talent:enhance-focus-enhance',
            'enhance-talent:enhance-potency-enhance-sm', 'enhance-talent:harden-weaken-enhance',
            'enhance-talent:improved-flexibility-enhance', 'enhance-talent:ravenous-weapon-enhance-sm',
            'enhance-talent:staunch-resistance-enhance', 'enhance-talent:superior-poison-enhance',
            'enhance-talent:superior-reflexes-enhance', 'enhance-talent:supply-vigor-enhance',
            'enhance-talent:traveling-weapon-enhance', 'talent:crippling-strike-strike',
            'talent:natural-enhancement')},
        'enhancement:talent:greater-enhance-equipment': 0,
        'enhancement:enhance-talent:physical-enhancement-enhance': 0,
        'enhancement:enhance-talent:mental-enhancement-enhance': 0,
        'life:talent:greater-restore-warden': 1,
        **{'creation:' + suffix: 1 for suffix in (
            'material-talent:gaseous-generation-material',
            'advanced-talent:corp-criadhach-dbh', 'advanced-talent:create-minds-think-alike-jester-s-hb',
            'advanced-talent:fabricate', 'advanced-talent:permanent-change',
            'alter-talent:change-material-alter', 'alter-talent:crack-alter-apoc',
            'alter-talent:forge-alter', 'alter-talent:rigidity-alter',
            'material-talent:acidic-creation-material', 'talent:larger-creation',
            'talent:lengthened-creation', 'talent:replication')},
        **{'creation:' + suffix: 0 for suffix in (
            # Base Create plus required Lengthened Creation already total two SP.
            'advanced-talent:create-materials',
            'advanced-talent:imperfect-recreation-alienist-hb', 'advanced-talent:integrate-item-alter-sm',
            'advanced-talent:internal-creation-apoc',
            'talent:practiced-creation',
            'material-talent:alchemical-creation-material',
            'talent:instill-alteration-instill',
            'talent:created-momentum',
            'advanced-talent:magma-mastery-material', 'advanced-talent:mythical-material-maker-material',
            'advanced-talent:state-shift-alter',
            'material-talent:object-of-force-material',
            'material-talent:expanded-materials-material', 'talent:distant-creation-range',
            'talent:divided-creation-mass', 'talent:exquisite-detail-utility',
            'talent:transmuting-strike-strike-3pp')},
        'creation:advanced-talent:costly-creation': 5,
        'life:talent:violent-recuperation-alienist-hb': 0,
        'life:talent:revitalize': 0,
        **{'life:' + suffix: 0 for suffix in (
            'cure-talent:restore-capacity-cure', 'cure-talent:restore-health-cure',
            'cure-talent:restore-senses-cure', 'cure-talent:restore-spirit-cure',
            'talent:affliction', 'talent:clarified-strike-strike', 'talent:fount-of-life',
            'talent:instill-life-instill', 'talent:ranged-healing-range', 'talent:sanctify')},
        'life:talent:mass-healing-mass': 1,
        'life:talent:restorative-cure': 1,
        'life:talent:self-renewal': 1,
        'life:talent:sudden-invigoration': 1,
        'life:talent:deeper-healing': 0,
        'life:talent:painkiller': 0,
        'life:talent:esoteric-healing': 0,
        'life:talent:latent-healing': 0,
        'life:talent:lingering-resilience': 0,
        'life:talent:lingering-vitality-warden': 0,
        'life:talent:resuscitate': 0,
        'life:talent:stabilizing-invigoration-warden': 0,
        'life:advanced-talent:hypervitalize': 2,
        'protection:talent:mass-aegis-mass': 1,
        'protection:advanced-talent:tripped-glyph-3pp': 2,
        'weather:talent:greater-weather': 1,
        'weather:talent:severe-weather': 1,
        'weather:advanced-talent:cacophonic-clap': 1,
        'weather:advanced-talent:climate': 1,
        'weather:advanced-talent:climatic-shift': 3,
        'weather:advanced-talent:dehydration-pulse': 2,
        'weather:advanced-talent:radiation-lord-cata-hb': 2,
        'weather:advanced-talent:rain-bomb': 1,
        'weather:advanced-talent:volcano-lord': 2,
        **{f'weather:advanced-talent:{suffix}': 0 for suffix in (
            'biohazard-cata-hb', 'boiling-lord', 'cold-lord',
            'contaminated-blows-mantle-radiation-cata-hb', 'contamination-lord-cata-hb',
            'desert-lord', 'fire-tornadoes', 'heat-lord',
            'interference-cloud-shroud-radiation-cata-hb', 'melt-skin-shroud-radiation-cata-hb',
            'radiotherapy-mantle-radiation-cata-hb', 'rain-lord', 'tornado-lord', 'wind-lord')},
        'time:talent:mass-time-mass': 1,
        'time:talent:augment-healing': 1,
        'time:talent:causality-time': 1,
        **{'time:talent:' + suffix: 0 for suffix in (
            'improved-haste', 'improved-slow', 'instill-time-instill', 'lingering-time-3pp',
            'ranged-time-range', 'time-strike-strike', 'time-zone')},
        'time:talent:delay-pain-time': 1,
        'time:talent:eject-time': 1,
        'time:talent:fast-time-time': 1,
        'time:talent:lethargy-time': 1,
        'time:talent:repetition-time': 1,
        'time:talent:retroactive-preparation': 1,
        'time:talent:second-chance': 1,
        'time:talent:temporal-trap': 1,
        'time:talent:time-bubble-time': 1,
        'time:talent:retry-time': 2,
        'time:talent:shift-time-time': 1,
        'time:talent:steal-time-time': 1,
        'time:talent:stretch-time-time': 1,
        'time:talent:time-freeze-time': 1,
        'time:advanced-talent:past-sight-utility': 1,
        'time:advanced-talent:query-self-utility': 2,
        'time:advanced-talent:reversion-utility': 10,
        'time:advanced-talent:temporal-haste': 1,
        'time:advanced-talent:temporal-stasis': 3,
        'destruction:blast-shape-talent:energy-aura-blast-shape': 1,
        'destruction:blast-shape-talent:energy-leap-blast-shape': 1,
        'destruction:blast-shape-talent:retributive-blast-blast-shape': 1,
        'destruction:advanced-talent:adaptive-admixture-sm': 1,
        'destruction:advanced-talent:disintegrate-blast-type': 1,
        'destruction:advanced-talent:energy-cloud-blast-shape': 3,
        'destruction:advanced-talent:greater-admixture': 1,
        'destruction:advanced-talent:calamity-blast-shape': 2,
        'destruction:advanced-talent:radiation-blast-blast-type-fire-light': 2,
        'destruction:advanced-talent:crystal-cocoon': 1,
        'destruction:advanced-talent:detonating-salvo-lg': 1,
        'warp:space-talent:teleport-beacon-space': 1,
        'warp:talent:segmented-warp': 1,
        'warp:space-talent:dimension-pierce-space': 1,
        'warp:space-talent:fluctuate-space': 1,
        'warp:advanced-talent:dimensional-lock-space': 2,
        'warp:advanced-talent:extradimensional-torpor-space-apoc': 1,
        'warp:advanced-talent:organ-detachment-space-alienist-hb': 3,
        'warp:advanced-talent:create-demiplane-utility': 3,
        'warp:advanced-talent:timeline-drift-lg': 2,
        # Time Warp's five-SP total replaces True Teleport's included two SP.
        'warp:advanced-talent:time-warp-jester-s-hb': 3,
        'warp:talent:emergency-teleport': 1,
        'warp:talent:instill-teleport-instill': 1,
        'warp:talent:mass-teleport-mass': 1,
        # Group's two-SP mode replaces Mass's one-SP mode; add only the difference.
        'warp:advanced-talent:group-teleport': 1,
        'warp:talent:unwilling-teleport': 1,
        'warp:advanced-talent:true-teleport': 2,
        'warp:advanced-talent:planeshift': 2,
        'warp:advanced-talent:portal': 1,
        'warp:advanced-talent:enduring-portal': 1,
        'protection:advanced-talent:antimagic-aura': 1,
        'protection:advanced-talent:antimagic-aura-arcforge-addendum-lg': 1,
        'protection:advanced-talent:spell-selectivity-arcforge-addendum-lg': 1,
        'protection:aegis-ward-talent:technological-suppression-aegis-ward-lg': 1,
        'protection:advanced-talent:automatic-fortification-3pp': 1,
        # Adaptation's two-SP aegis adds one beyond the ordinary one-SP aegis.
        'protection:advanced-talent:adaptation-aegis': 1,
        'protection:aegis-ward-talent:spell-ward-aegis-ward': 1,
        'protection:advanced-talent:spell-eater-aegis-3pp': 2,
        'protection:advanced-talent:spell-selectivity-dbh': 1,
        'protection:advanced-talent:undying-aegis': 1,
        'protection:succor-talent:negation-succor-3pp': 1,
        'protection:succor-talent:reflection-succor': 1,
    }.get(entry.get('key'), None if reviewed_only else 0)


def talent_choice_spell_points(key, choice):
    """Reviewed mode costs; None leaves an unrelated/manual value unchanged."""
    from app.marvelous_base_powers import TALENT_EFFECT_SP_CHOICES
    return TALENT_EFFECT_SP_CHOICES.get(key, {}).get(choice)


def talent_construction_cost(entry, *, additional_spell_points=0, mythic_crafter=False, base_power=None):
    """Default reviewed contribution; never extract spell-point rules from prose.

    Published Admixture construction is free; its blast types are paid separately.
    A single Dark meld replaces Darkness for free, except Feed On Darkness (+2).
    Other talents use the general ordinary/advanced rule until mapped explicitly.
    """
    if isinstance(additional_spell_points, bool) or not isinstance(additional_spell_points, int) or additional_spell_points < 0:
        raise ValueError('Additional spell points must be a nonnegative integer.')
    if not isinstance(mythic_crafter, bool): raise ValueError('Mythic Crafter access must be boolean.')
    from app.marvelous_base_powers import DARK_MELDS
    if base_power == 'dark:meld' and entry.get('key') in DARK_MELDS:
        return (2 if entry['key'] == 'dark:meld-talent:feed-on-darkness-meld' else 0) + additional_spell_points
    # A replacement ordinary sense costs one complexity per SP, not an extra
    # talent surcharge as well (Magical Items, Divination / Sense).
    if base_power == 'divination:sense' and entry.get('key', '').startswith('divination:sense-talent:'):
        return additional_spell_points
    if entry.get('key') == 'destruction:talent:admixture':
        return 0
    if entry.get('key') in {'alteration:talent:mass-alteration-mass', 'illusion:talent:suppression-glamer'}:
        return 2 + additional_spell_points
    return (2 if 'advanced' in str(entry.get('category', '')).casefold() and not mythic_crafter else 1) + additional_spell_points


def dark_meld_blueprint(entry, *, caster_level, uses, activation):
    """An ordinary meld as a separate, editable power; no persistence or catalog copy."""
    from app.marvelous_base_powers import DARK_MELDS
    if entry.get('key') not in DARK_MELDS:
        raise ValueError('Choose an ordinary Dark meld talent.')
    return dict(schema_version=1, sphere='Dark', base_power='dark:meld', caster_level=caster_level,
        uses=uses, activation=activation, range_steps=0, duration_steps=0, unique_changes=0,
        contributions=[dict(catalog_key=entry['key'], complexity=talent_construction_cost(entry, base_power='dark:meld'),
            additional_spell_points=0)], effect_name=entry['name'], effect_description='')


ACTIVATION_COMPLEXITY = {"standard": 0, "full-round": -1, "move": 3, "swift": 5}


def simple_tradition_reduction(plan):
    """Reviewed sample traditions; never infer boons from user/catalog prose."""
    tradition = plan.get('crafting_tradition')
    if tradition is None: return 0
    if not isinstance(tradition, dict) or not isinstance(tradition.get('key'), str):
        raise ValueError('Crafting tradition requires a catalog identity.')
    return int(tradition['key'] in {
        'crafting:evil-artifice', 'crafting:sacred-artifice'})


def educated_required_spheres(plan):
    """None when absent, empty when pending; names are catalog-validated on save."""
    tradition = plan.get('crafting_tradition')
    if tradition is not None and (not isinstance(tradition, dict) or not isinstance(tradition.get('key'), str)):
        raise ValueError('Crafting tradition requires a catalog identity.')
    required = ['Divination'] if (tradition or {}).get('key') == 'crafting:diviner-s-sight' else []
    present = bool(required)
    records = plan.get('drawbacks', [])
    if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
        raise ValueError('Drawbacks must be a list of records.')
    for row in records:
        if row.get('source') != 'published' or row.get('catalog_key') != 'crafting:educated': continue
        present = True
        selected = row.get('required_spheres', [])
        if (not isinstance(selected, list) or len(selected) > 3
                or any(not isinstance(name, str) or not name.strip() for name in selected)
                or len({name.strip().casefold() for name in selected}) != len(selected)):
            raise ValueError('Educated requires up to three distinct sphere names.')
        if not selected: return ()
        required.extend(name.strip() for name in selected)
    required = tuple({name.casefold(): name for name in required}.values())
    if len(required) > 3: raise ValueError('Educated requires up to three distinct sphere names.')
    return required if present else None


def complex_required_skill(plan):
    """Published Complex's chosen check; empty means an incomplete draft."""
    from app.models import SKILLS
    names = {skill.name.casefold(): skill.name for skill in SKILLS}
    for record in plan.get('drawbacks', []):
        if record.get('source') == 'published' and record.get('catalog_key') == 'crafting:complex':
            selected = record.get('required_skill', '')
            if not isinstance(selected, str) or (selected and selected.casefold() not in names):
                raise ValueError('Complex requires a known skill choice.')
            return names[selected.casefold()] if selected else ''
    return None


def crafting_item_limitations(plan):
    """Reviewed identities, independent of editable tradition/drawback prose."""
    keys = {row.get('catalog_key') for row in plan.get('drawbacks', []) if row.get('source') == 'published'}
    tradition = (plan.get('crafting_tradition') or {}).get('key')
    if tradition == 'crafting:evil-artifice': keys.update({'crafting:sacrificing', 'crafting:clingy'})
    if tradition == 'crafting:ley-linked': keys.add('crafting:taxing')
    if tradition in {'crafting:city-construction', 'crafting:cryptwood-artifice'}:
        keys.add('crafting:area-bound')
    if tradition == 'crafting:city-construction': keys.add('crafting:bulky')
    if tradition == 'crafting:cryptwood-artifice': keys.add('crafting:clingy')
    return keys


def complex_crafting_skills(plan):
    """Skill training required by the selected published restriction/tradition."""
    required = {'crafting:fey-touched': ('Knowledge (nature)',),
                'crafting:ridiculously-complicated': ('Acrobatics', 'Disable Device', 'Linguistics', 'Use Magic Device')}.get(
                    (plan.get('crafting_tradition') or {}).get('key'), ())
    chosen = complex_required_skill(plan)
    extra = complex_additional_skills(plan)
    return tuple(dict.fromkeys((*required, *((chosen,) if chosen else ()), *extra)))


def crafting_boon_details(plan):
    """Published sample-tradition effects without invented durability or clocks."""
    key = (plan.get('crafting_tradition') or {}).get('key')
    if key in {'crafting:city-construction', 'crafting:evil-artifice'}:
        return ('Resilient: +2 hardness and 25% more item HP (round down, minimum 1). Apply to the actual item material; no baseline durability is assumed. Armor also has a 25% chance to negate extra critical-hit damage, without stacking with fortification or similar effects.',)
    if key == 'crafting:fey-touched':
        return ('Living: repairs 1 item HP per day after at least 8 continuous hours with suitable nutrients; broken items require two days per HP. Nutrients depend on material: bone, leather/hide, soil/sunlight for wood, or ore/ingot for metal. Exposure and repair are tracked manually.',)
    if key == 'crafting:ley-linked':
        return ('Ley-Charged: atop a leyline, the GM chooses +2 effective caster levels, +1 to the normal effect/save DC, or a comparable benefit. This conditional use bonus is not a permanent construction CL or an automatic price adjustment.',)
    if key == 'crafting:cryptwood-artifice':
        surcharge = ()
        if marvelous_item_weight(plan) is not None:
            cost = Fraction(str(plan['base_weight_lb'])) * 25
            surcharge = (f'Conditional Greenwood surcharge: {float(cost):g} gp = {plan["base_weight_lb"]:g} original lb × 25 gp/lb. Applies only to an eligible wooden/masterwork item, not another special material; add base/masterwork costs separately. Not included in the magical-effect quote.',)
        return (
            'Imbued (greenwood): suitable wooden or mostly wooden items gain greenwood benefits; items already made from another special material are ineligible. Do not assume the custom device is a suitable wooden item.',
            'Greenwood: while damp and touching fertile soil, repairs 1 item HP per hour, including breaks; broken condition repairs during the first hour. Takes one-quarter fire damage. Wood-shaping magic lasts twice as long. Water/soil exposure and repairs remain manual; no time tracking is added.',
            'Material cost review: Imbued charges half the normal special-material surcharge. Greenwood normally adds 50 gp per original pound to a masterwork item, so review 25 gp per original pound plus the applicable base/masterwork costs separately. These underlying-item costs are not included in the magical-effect quote.',
        ) + surcharge
    return ()


def complex_additional_skills(plan):
    """Additional activation rolls for repeat selections; legacy drafts need none."""
    from app.models import SKILLS
    names = {skill.name.casefold(): skill.name for skill in SKILLS}
    result = []
    for record in plan.get('drawbacks', []):
        if record.get('source') != 'published' or record.get('catalog_key') != 'crafting:complex': continue
        selected = record.get('additional_skills', [])
        if not isinstance(selected, list) or any(not isinstance(name, str) or name.casefold() not in names for name in selected):
            raise ValueError('Complex additional checks require known skills.')
        result.extend(names[name.casefold()] for name in selected)
    return tuple(result)


def marvelous_item_weight(plan):
    """Resolve an explicitly supplied base weight; unknown is not zero."""
    value = plan.get('base_weight_lb')
    if value is None: return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('Base item weight must be a finite nonnegative number.')
    from math import isfinite
    try:
        weight = float(value) * (200 if 'crafting:bulky' in crafting_item_limitations(plan) else 1)
    except OverflowError as error:
        raise ValueError('Base item weight is too large.') from error
    if not isfinite(weight) or weight < 0:
        raise ValueError('Base item weight must be a finite nonnegative number.')
    return weight


def marvelous_area_bound_mode(plan):
    if 'crafting:area-bound' not in crafting_item_limitations(plan): return None
    mode = plan.get('area_bound_mode', '')
    if mode not in ('', 'distance', 'recharge'):
        raise ValueError('Choose distance or location recharge for Area-Bound.')
    return mode


def spell_selectivity_options(plan):
    """Reviewed DbH sphere-selection mode; source-type variants remain separate."""
    rows = [row for row in plan.get('contributions', [])
            if row.get('catalog_key') == 'protection:advanced-talent:spell-selectivity-dbh']
    if not rows: return None
    row = rows[0]
    mode, spheres = row.get('effect_choice', ''), row.get('effect_spheres', [])
    if mode not in {'', 'only', 'except'} or not isinstance(spheres, list) or any(
            not isinstance(name, str) or not name.strip() for name in spheres):
        raise ValueError('Spell Selectivity requires a valid mode and sphere list.')
    if len({name.casefold() for name in spheres}) != len(spheres) or len(spheres) > 1 + plan['caster_level'] // 5:
        raise ValueError('Spell Selectivity sphere choices exceed the limit or contain duplicates.')
    from app.marvelous_base_powers import ANTIMAGIC_AURA_KEYS
    if mode == 'except' and any(item.get('catalog_key') in ANTIMAGIC_AURA_KEYS and contributions_can_coexist(row, item)
                               for item in plan['contributions']):
        raise ValueError('Spell Selectivity except-mode cannot be combined with Antimagic Aura.')
    return dict(mode=mode, spheres=tuple(spheres), maximum=1 + plan['caster_level'] // 5)


def crafting_limitation_details(plan, *, quotation=None):
    """Concrete item requirements; no location, clock or sacrifice simulation."""
    keys = crafting_item_limitations(plan)
    lines = []
    if 'crafting:unwieldy' in keys:
        penalty = min(6, 1 + plan['caster_level'] // 4)
        lines.append(f'Unwieldy: −{penalty} to attack rolls made with this item or skill checks using it; stacks with other penalties. If caster level is modified, use the worse penalty; apply manually.')
    if 'crafting:clingy' in keys:
        lines.append(f'Clingy: curse suppression normally requires a check against DC {10 + plan["caster_level"]}; suppression/removal is resolved manually.')
    bound = marvelous_area_bound_mode(plan)
    if bound == 'distance':
        lines.append(f'Area-Bound: functions only within {plan["caster_level"]} miles of the bonded location (a smaller distance may be chosen); location is checked manually.')
    elif bound == 'recharge':
        lines.append('Area-Bound: recharge at the bonded location for at least 5 minutes, at most once per day. Without daily uses, recharge every 24 hours; location and elapsed time are manual.')
    elif bound == '':
        lines.append('Area-Bound: choose distance-limited use or location recharge before resolving recovery.')
    if 'crafting:charged' in keys:
        complexity, _, _ = quotation if quotation is not None else quote_marvelous_blueprint(plan)
        points = sum(row.get('additional_spell_points', 0) for row in plan['contributions'] if not row.get('alternative'))
        points += sum(row.get('additional_spell_points', 0) for row in plan.get('feat_integrations', []))
        scope = ' (primary power only)' if plan.get('extra_effects') else ''
        if any(row.get('alternative') for row in plan['contributions']):
            lines.append(f'Charged{scope}: {complexity + points} base charges per activation, plus the additional SP of the selected alternative in each group; charge supply is manual.')
        else:
            lines.append(f'Charged{scope}: {complexity + points} charges per activation; charge supply is manual.')
        if plan.get('extra_effects'):
            lines.append('Charged: multi-power charge accounting needs GM review; the primary-power figure is not a whole-item activation total.')
    if 'crafting:sacrificing' in keys:
        lines.append(f'Sacrificing: recharge requires a qualifying sacrifice of at least {(plan["caster_level"] + 1) // 2} HD; once per day, manually verified.')
    if 'crafting:taxing' in keys:
        lines.append('Taxing: concentration is required when applicable; use normal concentration or half HD (rounded down, minimum 1), whichever is higher.')
    tradition = (plan.get('crafting_tradition') or {}).get('key')
    skills = {'crafting:fey-touched': ('Knowledge (nature)',),
              'crafting:ridiculously-complicated': ('Acrobatics', 'Disable Device', 'Linguistics', 'Use Magic Device')}.get(tradition, ())
    if skills:
        lines.append(f'Complex: DC {5 + plan["caster_level"]} {", ".join(skills)} checks to activate; crafter must be trained in each skill.')
    skill = complex_required_skill(plan)
    if skill:
        lines.append(f'Complex: DC {5 + plan["caster_level"]} {skill} check as part of activation; crafter must be trained in this skill. Resolve the activation check manually.')
        for extra in complex_additional_skills(plan):
            lines.append(f'Complex: additional DC {5 + plan["caster_level"]} {extra} check on every activation; resolve manually.')
    elif skill == '': lines.append('Complex: choose the required skill before completing this design.')
    if educated := educated_required_spheres(plan):
        lines.append('Educated: user must be trained in every required sphere: ' + ', '.join(educated) + '; Use Magic Device cannot bypass this requirement.')
    elif educated == ():
        lines.append('Educated: choose required spheres before using or completing this design.')
    return tuple(lines)


def marvelous_manual_recharge_requirements(plan):
    """Only reviewed replacement recovery contracts; no inferred clock state."""
    requirements = []
    if 'crafting:sacrificing' in crafting_item_limitations(plan):
        requirements.append(f'Qualifying sacrifice of at least {(plan["caster_level"] + 1) // 2} HD, killed by coup de grace with the item within 5 feet; at most once per day. Verify any tradition-specific exceptions with the GM.')
    if marvelous_area_bound_mode(plan) == 'recharge':
        requirements.append('Item remained at its specified bonded recharge location for at least 5 minutes; recharge is allowed at most once per day. Verify the location and elapsed time manually.')
    return tuple(requirements)


def marvelous_recovers_on_rest(plan):
    return marvelous_area_bound_mode(plan) != '' and not marvelous_manual_recharge_requirements(plan)


def effect_complexity(*, talent_costs=(), alternative_costs=(), range_steps=0,
                      duration_steps=0, activation="standard", unique_changes=0):
    """Resolve explicit construction contributions, never infer them from prose.

    Talent costs include the talent's own complexity and extra spell points.
    Alternative costs represent mutually exclusive options: the largest is paid
    in full and the others at half cost. Sphere-specific exceptions must supply
    their published costs rather than the general one-point talent default.
    """
    activation_cost = ACTIVATION_COMPLEXITY
    if activation not in activation_cost:
        raise ValueError("Unsupported activation time.")
    for value in (range_steps, duration_steps, unique_changes):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("Construction steps must be integers.")
    costs = tuple(talent_costs)
    alternatives = tuple(alternative_costs)
    for value in (*costs, *alternatives):
        if isinstance(value, bool) or not isinstance(value, (int, Fraction)) or value < 0:
            raise ValueError("Effect contributions must be nonnegative exact values.")
    variable = (sum(alternatives) + max(alternatives)) / Fraction(2) if alternatives else 0
    return max(Fraction(1), Fraction(1 + sum(costs) + variable + range_steps
                                   + 2 * duration_steps + activation_cost[activation]
                                   + unique_changes))


def drawback_complexity(records):
    """Explicit reviewed reductions; published text alone never implies a price."""
    if not isinstance(records, list): raise ValueError('Drawbacks must be a list.')
    seen, total = set(), 0
    for record in records:
        if not isinstance(record, dict) or record.get('source') not in {'published', 'custom'}:
            raise ValueError('Each drawback needs a published/custom source.')
        name, reduction = record.get('name'), record.get('reduction')
        if not isinstance(name, str) or not name.strip() or not isinstance(record.get('description', ''), str):
            raise ValueError('Drawbacks require a name and text description.')
        identity = record.get('catalog_key') if record['source'] == 'published' else name.strip().casefold()
        if not isinstance(identity, str) or not identity or identity in seen:
            raise ValueError('Duplicate or missing drawback identity.')
        seen.add(identity)
        if isinstance(reduction, bool) or not isinstance(reduction, int) or not 0 <= reduction <= 100:
            raise ValueError('Drawback reduction must be an integer from 0 to 100.')
        total += reduction
    return total


def light_lens_conversion_complexity(plan):
    """One lens conversion, already paid by a selected lens talent's row."""
    from app.marvelous_base_powers import LIGHT_LENSES
    return int(plan.get('base_power') == 'light:lens' and not any(
        row.get('catalog_key') in LIGHT_LENSES for row in plan.get('contributions', [])))


def instill_alteration_minimum_complexity(plan):
    """A free alter costs one SP when instilled; paid alters pay no extra point."""
    rows = plan.get('contributions', [])
    instill = [row for row in rows if row.get('catalog_key') == 'creation:talent:instill-alteration-instill']
    if not instill: return 0
    if plan.get('base_power') != 'creation:alter':
        raise ValueError('Instill Alteration requires a Creation alter effect.')
    if len(instill) != 1 or instill[0].get('alternative'):
        raise ValueError('Instill Alteration must be one fixed talent contribution; duplicates or optional instilling need cost review.')
    if any(row.get('additional_spell_points', 0) for row in rows if not row.get('alternative')): return 0
    groups = {}
    for row in rows:
        if row.get('alternative'): groups.setdefault(row.get('alternative_group', 1), []).append(row)
    if not groups: return 1
    if any(all(row.get('additional_spell_points', 0) for row in group) for group in groups.values()): return 0
    if len(groups) != 1:
        raise ValueError('Instill Alteration with interacting alternative groups needs cost review.')
    options = next(iter(groups.values()))
    before = [row['complexity'] for row in options]
    after = [row['complexity'] + int(not row.get('additional_spell_points', 0)) for row in options]
    return effect_complexity(alternative_costs=after) - effect_complexity(alternative_costs=before)


def practiced_creation_complexity_reduction(plan):
    """Only extra-SP complexity can be reduced; the fixed base cost stays intact."""
    rows = plan.get('contributions', [])
    selected = [row for row in rows if row.get('catalog_key') == 'creation:talent:practiced-creation']
    if not selected: return 0
    if plan.get('base_power') != 'creation:create' or plan.get('activation') != 'full-round':
        raise ValueError('Practiced Creation requires Create with full-round activation instead of its normal standard action.')
    if len(selected) != 1 or any(row.get('alternative') for row in rows):
        raise ValueError('Practiced Creation with duplicate or alternative effects needs cost review.')
    incompatible = {'creation:talent:lengthened-creation', 'creation:talent:replication',
        'creation:advanced-talent:create-materials', 'creation:advanced-talent:permanent-change'}
    if any(row.get('catalog_key') in incompatible for row in rows):
        raise ValueError('Practiced Creation requires concentration-only maintenance, not sustained or instantaneous creation.')
    return int(any(row.get('additional_spell_points', 0) for row in rows))


def conjuration_duration_complexity(plan):
    """The two talent rows pay +2; the optional 24-hour conversion adds +2."""
    from app.marvelous_base_powers import conjuration_item_duration
    return 2 if conjuration_item_duration(plan) == 'fixed-day' else 0


def quote_marvelous_blueprint(plan):
    """Price the persisted composer blueprint using the same pure rules."""
    from app.marvelous_base_powers import FATE_IMMEDIATE_WORDS, effective_base_duration
    if plan.get('schema_version') != 1:
        raise ValueError('Unsupported Marvelous blueprint version.')
    spell_selectivity_options(plan)
    educated_required_spheres(plan)
    complex_required_skill(plan)
    complex_additional_skills(plan)
    if plan.get('base_power'):
        from app.marvelous_base_powers import resolve_base_power
        resolve_base_power(plan)
    elif plan.get('effect_range_steps', 0):
        raise ValueError('Effect range adjustments require a structured base power.')
    for option in ('permanent', 'no_space_limitation', 'full_blast_damage'):
        if not isinstance(plan.get(option, False), bool):
            raise ValueError('Construction flags must be boolean.')
    if plan.get('permanent') and not plan.get('base_power'):
        raise ValueError('Permanency requires a structured base power.')
    if any(not isinstance(x.get('alternative', False), bool) for x in plan['contributions']):
        raise ValueError('Alternative-effect flags must be boolean.')
    groups = {}
    immediate_word = plan.get('base_power') == 'fate:word' and any(
        row.get('catalog_key') in FATE_IMMEDIATE_WORDS for row in plan['contributions'])
    for contribution in plan['contributions']:
        if plan.get('base_power') == 'fate:word':
            if contribution.get('catalog_key') == 'fate:talent:shrieking-strike-strike' and immediate_word:
                raise ValueError('Shrieking Strike cannot affect a word normally usable as an immediate action, even after an activation adjustment.')
            if (contribution.get('catalog_key') == 'fate:talent:instill-fate-instill'
                    and (immediate_word or effective_base_duration(plan) == 'concentration')):
                raise ValueError('Instill Fate cannot contain a concentration word or a word with a native immediate-action trigger.')
        if (contribution.get('catalog_key') == 'creation:advanced-talent:sustenance-material-utility'
                and contribution.get('effect_choice') == 'standard-action food and drink'
                and plan.get('base_power') != 'creation:alter'):
            raise ValueError('Sustenance food mode replaces the Creation Alter effect; choose creation:alter.')
        if contribution.get('catalog_key') == 'creation:advanced-talent:plasma-projection':
            from app.marvelous_base_powers import PLASMA_PROJECTION_BASE_MODES
            expected = PLASMA_PROJECTION_BASE_MODES.get(contribution.get('effect_choice'))
            if expected and plan.get('base_power') != expected:
                raise ValueError('Plasma Projection mode requires base power ' + expected + '.')
        if (contribution.get('catalog_key') in {'time:talent:time-strike-strike', 'life:talent:clarified-strike-strike',
                'creation:talent:transmuting-strike-strike-3pp', 'dark:talent:shadow-strike-strike-3pp',
                'divination:talent:revealing-strike-strike-3pp', 'blood:talent:exsanguinating-strike-strike-bap',
                'fallen-fey:talent:feytouch-strike-strike-3pp', 'fate:talent:shrieking-strike-strike'}
                and plan['activation'] in {'move', 'swift'}):
            raise ValueError('Strike talents cannot reduce casting below a standard action.')
        if (contribution.get('catalog_key') == 'enhancement:advanced-talent:inherent-enhancement-enhance-archmagi-s-hb'
                and contribution.get('effect_choice', '').startswith('temporary untyped bonus: ')
                and (plan.get('permanent') or plan['duration_steps'] > 0)):
            raise ValueError('Temporary Inherent Enhancement cannot exceed one round per caster level or become permanent.')
        if (plan.get('base_power') == 'mana:manipulate'
                and contribution.get('catalog_key') == 'mana:manipulation-talent:transfer-manipulation'):
            raise ValueError('Mana Transfer cannot be applied to a crafted manipulate effect.')
        extra_sp = contribution.get('additional_spell_points', 0)
        if isinstance(extra_sp, bool) or not isinstance(extra_sp, int) or extra_sp < 0 or extra_sp > contribution['complexity']:
            raise ValueError('Additional spell points must be included in the contribution complexity.')
        group = contribution.get('alternative_group', 1)
        if isinstance(group, bool) or not isinstance(group, int) or group < 1:
            raise ValueError('Alternative groups must be positive integers.')
        if contribution.get('alternative', False):
            groups.setdefault(group, []).append(contribution['complexity'])
    # Resolve each independent choice set separately; legacy alternatives use group 1.
    grouped_costs = [effect_complexity(alternative_costs=costs) - 1 for costs in groups.values()]
    feat_cost = feat_integration_complexity(plan.get('feat_integrations', []))
    simple = simple_tradition_reduction(plan)
    marvelous_item_weight(plan)
    marvelous_area_bound_mode(plan)
    limitations = crafting_item_limitations(plan)
    for power in [plan, *plan.get('extra_effects', [])]:
        if 'crafting:charged' in limitations and power['uses'] != 5:
            raise ValueError('Charged requires an unlimited-use Marvelous Item.')
        if 'crafting:sacrificing' in limitations and power['uses'] not in (1, 2, 3, 4):
            raise ValueError('Sacrificing requires limited daily uses, not unlimited or fifty-total uses.')
        if 'crafting:taxing' in limitations and power.get('permanent'):
            raise ValueError('Taxing cannot restrict an effect usable for an unlimited duration.')
    complexity = effect_complexity(talent_costs=[x['complexity'] for x in plan['contributions'] if not x.get('alternative', False)] + grouped_costs + [instill_alteration_minimum_complexity(plan)],
        range_steps=plan['range_steps'], duration_steps=plan['duration_steps'],
        activation=plan['activation'], unique_changes=plan['unique_changes'] - drawback_complexity(plan.get('drawbacks', [])) - simple + (2 if plan.get('permanent') else 0) + int(plan.get('full_blast_damage', False)) + 2 * plan.get('effect_range_steps', 0) + feat_cost + light_lens_conversion_complexity(plan) - practiced_creation_complexity_reduction(plan) + conjuration_duration_complexity(plan))
    price = marvelous_item_price(plan['caster_level'], complexity,
                                daily_uses=1 if plan['uses'] == 50 else plan['uses'], limited_uses=plan['uses'] == 50)
    if plan.get('no_space_limitation'):
        price = replace(price, market_price_gp=price.market_price_gp * 2)
    if plan.get('extra_effects'):
        if any(row.get('source') == 'published' and row.get('catalog_key', '').startswith('crafting:')
               for extra in plan['extra_effects'] for row in extra.get('drawbacks', [])):
            raise ValueError('Crafting-specific drawbacks belong to the whole item, not individual powers.')
        if any(extra.get('extra_effects') for extra in plan['extra_effects']):
            raise ValueError('Nested effect combinations are not supported.')
        combined = quote_marvelous_effects(marvelous_pricing_powers(plan), mode=plan.get('combination_mode', 'multiple'))
        price = replace(price, market_price_gp=combined['market_price_gp'])
    quote = marvelous_crafting_quote(price, plan['caster_level'])
    tradition = plan.get('crafting_tradition')
    cheap = False
    if tradition is not None:
        cheap = tradition['key'] in {'crafting:city-construction', 'crafting:diviner-s-sight'}
        if tradition['key'] in {'crafting:city-construction', 'crafting:evil-artifice'} and any(
                row.get('source') == 'published' and row.get('catalog_key') == 'crafting:fragile'
                for row in plan.get('drawbacks', [])):
            raise ValueError('Fragile is incompatible with the Resilient boon of this crafting tradition.')
    expensive = any(record['source'] == 'published' and record.get('catalog_key') == 'crafting:expensive'
                    for record in plan.get('drawbacks', []))
    if cheap or expensive:
        materials, selling = tradition_costs(price.market_price_gp, cheap=cheap, expensive=expensive)
        price = replace(price, market_price_gp=selling)
        quote = replace(quote, cost_gp=float(materials))
    return complexity, price, quote


def marvelous_remaining_uses(metadata, effect_index=0):
    """None means unlimited; limited-total charges never recover on rest."""
    plan = marvelous_effect_plan(metadata['marvelous_blueprint'], effect_index)
    _, price, _ = quote_marvelous_blueprint(plan)
    used = metadata.get('marvelous_uses_used', 0) if effect_index == 0 else metadata.get('marvelous_extra_uses_used', {}).get(str(effect_index), 0)
    if isinstance(used, bool) or not isinstance(used, int) or used < 0:
        raise ValueError('Invalid saved Marvelous Item usage.')
    maximum = price.daily_uses if price.daily_uses is not None else price.total_uses
    return None if maximum is None else max(0, maximum - used)


def marvelous_effect_plan(plan, effect_index=0):
    if isinstance(effect_index, bool) or not isinstance(effect_index, int) or effect_index < 0:
        raise ValueError('Invalid effect index.')
    if effect_index == 0:
        return {key: value for key, value in plan.items() if key not in {'extra_effects', 'combination_mode'}}
    extras = plan.get('extra_effects', [])
    if effect_index > len(extras): raise ValueError('Unknown item effect.')
    result = dict(extras[effect_index - 1])
    if simple_tradition_reduction(plan):
        result['crafting_tradition'] = plan['crafting_tradition']
    return result


def marvelous_pricing_powers(plan):
    """Apply per-effect Simple before combining, whole-item Cheap afterwards."""
    powers = [marvelous_effect_plan(plan, index) for index in range(1 + len(plan.get('extra_effects', [])))]
    if not simple_tradition_reduction(plan):
        powers = [{key: value for key, value in power.items() if key != 'crafting_tradition'} for power in powers]
    return powers


def quote_marvelous_effects(plans, *, mode='multiple'):
    """Quote independent or mixed powers without flattening their mechanics.

    Each entry is an ordinary single-effect blueprint. One most expensive
    effect is paid in full; the others cost 3/2 (multiple) or 2 (mixed).
    Creation eligibility and individual activation resources remain separate.
    """
    if mode not in {'multiple', 'mixed'}:
        raise ValueError('Unsupported effect combination mode.')
    plans = tuple(plans)
    if not plans:
        raise ValueError('At least one effect is required.')
    from app.marvelous_base_powers import effective_item_activation
    timings = {effective_item_activation(plan) for plan in plans}
    if mode == 'mixed' and 'immediate' in timings and len(timings) > 1:
        raise ValueError('A mixed native immediate word cannot accelerate a differently timed power for free; use separate powers or matching explicit activation adjustments.')
    levels = {plan['caster_level'] for plan in plans}
    if len(levels) != 1:
        raise ValueError('All item effects must have the same caster level.')
    quoted = tuple(quote_marvelous_blueprint(plan) for plan in plans)
    prices = tuple(result[1].market_price_gp for result in quoted)
    multiplier = Fraction(3, 2) if mode == 'multiple' else Fraction(2)
    highest = max(prices)
    total = highest + (sum(prices) - highest) * multiplier
    cl = plans[0]['caster_level']
    # This aggregate is only a construction quote, not a shared usage pool.
    combined = MarvelousItemPrice(total, 10 + cl // 2, None, None)
    return dict(effects=quoted, market_price_gp=total,
                crafting=marvelous_crafting_quote(combined, cl), mode=mode)


def marvelous_complexity_formula(plan, *, quotation=None):
    """Explain every primary-effect term; use the quote for the final result."""
    complexity, _, _ = quotation if quotation is not None else quote_marvelous_blueprint(plan)
    ordinary = [row for row in plan['contributions'] if not row.get('alternative')]
    groups = {}
    for row in plan['contributions']:
        if row.get('alternative'):
            groups.setdefault(row.get('alternative_group', 1), []).append(row['complexity'])
    terms = [('base', 1), ('talents', sum(row['complexity'] - row.get('additional_spell_points', 0) for row in ordinary)),
             ('extra SP', sum(row.get('additional_spell_points', 0) for row in ordinary)),
             ('lens conversion', light_lens_conversion_complexity(plan)),
             ('24-hour Conjuration', conjuration_duration_complexity(plan)),
             ('instill minimum SP', instill_alteration_minimum_complexity(plan)),
             ('Practiced extra-SP reduction', -practiced_creation_complexity_reduction(plan)),
             ('choices', sum(effect_complexity(alternative_costs=costs) - 1 for costs in groups.values())),
             ('range', plan['range_steps']), ('duration', 2 * plan['duration_steps']),
             ('activation', ACTIVATION_COMPLEXITY[plan['activation']]), ('unique changes', plan['unique_changes']),
             ('permanency', 2 if plan.get('permanent') else 0), ('full blast', int(plan.get('full_blast_damage', False))),
             ('distance/area', 2 * plan.get('effect_range_steps', 0)),
             ('feats', feat_integration_complexity(plan.get('feat_integrations', []))),
             ('drawbacks', -drawback_complexity(plan.get('drawbacks', []))),
             ('Simple boon', -simple_tradition_reduction(plan))]
    rendered = '1 base' + ''.join(f" {'+' if value > 0 else '−'} {abs(value)} {label}" for label, value in terms[1:] if value)
    from app.marvelous_base_powers import effective_item_activation
    native = '; native immediate word, no activation surcharge' if effective_item_activation(plan) == 'immediate' else ''
    return f'max(1, {rendered}) = {complexity}' + native


def marvelous_materials_formula(plan, *, quotation=None):
    """Explain the construction materials separately from selling price."""
    _, price, quote = quotation if quotation is not None else quote_marvelous_blueprint(plan)
    expensive = any(row.get('source') == 'published' and row.get('catalog_key') == 'crafting:expensive'
                    for row in plan.get('drawbacks', []))
    factor = ' × 1.25 (Expensive)' if expensive else ''
    return f'{price.market_price_gp} gp ÷ 2{factor} = {float(quote.cost_gp):g} gp'


def marvelous_price_formula(plan, *, quotation=None):
    """Readable live formula from the authoritative quote, not a second calculator."""
    complexity, price, _ = quotation if quotation is not None else quote_marvelous_blueprint(plan)
    tradition = plan.get('crafting_tradition') or {}
    if tradition.get('key') in {'crafting:city-construction', 'crafting:diviner-s-sight'}:
        base = {key: value for key, value in plan.items() if key != 'crafting_tradition'}
        return marvelous_price_formula(base) + f' → × 0.9 (Cheap) = {price.market_price_gp} gp'
    if plan.get('extra_effects'):
        amounts = [quote_marvelous_blueprint(power)[1].market_price_gp for power in marvelous_pricing_powers(plan)]
        highest = max(amounts)
        factor = '2' if plan.get('combination_mode') == 'mixed' else '1.5'
        return f'{highest} + ({sum(amounts)} − {highest}) × {factor} = {price.market_price_gp} gp'
    usage = '2.5 (50 total uses)' if plan['uses'] == 50 else f"{plan['uses']}" + (' (unlimited)' if plan['uses'] == 5 else ' (daily uses)')
    slot = ' × 2 (slotless)' if plan.get('no_space_limitation') else ''
    return f"400 gp × {plan['caster_level']} (CL) × {complexity} (complexity) × {usage}{slot} = {price.market_price_gp} gp"


def marvelous_crafting_quote(price: MarvelousItemPrice, caster_level: int, *,
                              missing_talents=0, adventuring=False,
                              distracting=False, requirements=None) -> CraftingQuote:
    """Spheres construction estimate; prerequisite eligibility is checked separately.

    Missing ordinary talents can raise the DC. Base spheres, advanced talents,
    creation feats and protected class requirements cannot use this bypass.
    Adventuring already includes distractions; do not apply both penalties.
    """
    for value in (caster_level, missing_talents):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("Crafting values must be nonnegative integers.")
    if caster_level < 1 or price.market_price_gp <= 0:
        raise ValueError("Caster level and price must be positive.")
    if requirements is not None:
        if missing_talents:
            raise ValueError("Use the validated requirements, not a second missing-talent count.")
        if not requirements.eligible:
            raise ValueError("Construction requirements are not met: " + "; ".join(requirements.blockers))
    dc_increase = requirements.dc_increase if requirements is not None else 5 * missing_talents
    # Work is proportional to price; whole calendar days are a presentation
    # estimate, not extra required crafting time.
    days = float(max(Fraction(1), price.market_price_gp / 1000))
    days *= 4 if adventuring else 2 if distracting else 1
    return CraftingQuote(price.market_price_gp / 2, 10 + caster_level + dc_increase,
                         days, "One item per day; materials paid at the start. Missing base spheres and advanced talents cannot be bypassed.")
