FORMULA_CODEX_HTML = """
<h1>Sheet Formula Language</h1>
<p>Formula-aware numeric fields, Custom Calculated Values, Counters, and Resource Pools use one small safe formula language. In an ordinary numeric field, start the expression with <code>=</code>; tracker formula boxes also accept the expression without it. A formula reads character values by stable name and does not depend on where a box is placed, how it is colored, or what its visible title is.</p>

<h2>Autocomplete</h2>
<p>Start a numeric formula with <code>=</code> and begin typing. Formula fields display matching references and functions together with their current value and a short explanation. Use the Up and Down arrows to select an entry, Enter or Tab to insert it, and Escape to close the menu. Custom Tracker and Building Block formula editors provide the same menu without requiring the leading equals sign.</p>

<h2>Where formulas can be used</h2>
<p>The same live formula editor is available for calculated sheet inputs: attack and damage bonuses; movement bases; manual maximum HP; maximum martial focus; casting-class levels, caster level, casting adjustments, and spell-point maximum/adjustment; skill miscellaneous bonuses; sphere-specific caster-level and DC adjustments; custom modifiers; custom feat and trait bonuses; and equipment weight, value, AC, maximum Dexterity, armor-check penalty, and enhancement.</p>
<p>Current HP, current spell points, temporary values, quantities, class levels, skill ranks, and prepared copies remain direct counters. They represent player actions or owned units rather than calculated statistics. Use a calculated pool or a formula-bearing maximum when a campaign needs a custom progression.</p>
<p>Saved formulas remain attached to their rule field when a block is moved, resized, recolored, or shown on another sheet type. Invalid formulas keep their last literal fallback and display an error for correction.</p>

<h2>Quick examples</h2>
<p>Engineering devices use stable per-record references such as <code>devices.device_12.active</code>, <code>devices.device_12.hp.current</code>, <code>devices.device_12.hp.maximum</code>, <code>devices.device_12.charges</code>, <code>devices.device_12.level</code>, <code>devices.device_12.effective_level</code>, and <code>devices.device_12.rounds_remaining</code>. Replace 12 with the device ID shown by autocomplete. State flags also include worn, broken, destroyed, depleted and abandoned. Charges refer only to the selected device, not its attached batteries.</p>
<table cellspacing="7">
<tr><th>Formula</th><th>What it does</th><th>Example result</th></tr>
<tr><td><code>floor(character.level / 3)</code></td><td>One point for every three total character levels.</td><td>Level 8 gives 2.</td></tr>
<tr><td><code>abilities.wisdom.modifier + character.level</code></td><td>Adds the current Wisdom modifier to total level.</td><td>Level 5 and Wisdom +4 gives 9.</td></tr>
<tr><td><code>max(1, abilities.charisma.modifier)</code></td><td>Uses the Charisma modifier, but never returns less than 1.</td><td>Charisma −1 gives 1.</td></tr>
<tr><td><code>trackers.ki_pool.maximum + 2</code></td><td>Builds one custom value from another tracker’s calculated maximum.</td><td>A Ki maximum of 6 gives 8.</td></tr>
<tr><td><code>character.level if abilities.intelligence.modifier &gt;= 3 else 0</code></td><td>Returns level only while Intelligence is at least +3.</td><td>Level 7 and Intelligence +4 gives 7.</td></tr>
<tr><td><code>-floor((bab + 3) / 4) if feats.power_attack else 0</code></td><td>A BAB-scaled value that exists only while Power Attack is enabled.</td><td>BAB +6 with the feat enabled gives −2.</td></tr>
<tr><td><code>skillranks.acrobatics + (2 if martial_focus else 0)</code></td><td>Combines ranks with a yes/no martial-focus test.</td><td>5 ranks while focused gives 7.</td></tr>
<tr><td><code>IF(feats.power_attack, -2, 0)</code></td><td>Excel-style conditional: use one value when a condition is true and another when it is false.</td><td>Power Attack enabled gives −2.</td></tr>
<tr><td><code>3d8 * floor(5 / 3)</code></td><td>Rolls three eight-sided dice, then applies ordinary formula arithmetic.</td><td>At 5 in this example, the result is one 3d8 roll.</td></tr>
</table>

<h2>Character references</h2>
<table cellspacing="7">
<tr><th>Reference</th><th>Meaning</th></tr>
<tr><td><code>character.level</code> or <code>character.total_level</code></td><td>Total levels across all classes.</td></tr>
<tr><td><code>character.bab</code></td><td>Current total base attack bonus.</td></tr>
<tr><td><code>bab</code></td><td>Short form of <code>character.bab</code>.</td></tr>
<tr><td><code>classes.monk.level</code></td><td>Total levels in the named class. Class names are lowercase; spaces and punctuation become underscores.</td></tr>
<tr><td><code>abilities.wisdom.score</code></td><td>The current final ability score, including active bonuses.</td></tr>
<tr><td><code>abilities.wisdom.modifier</code></td><td>The current ability modifier. <code>.mod</code> is an equivalent shorter name.</td></tr>
<tr><td><code>casting.caster_level</code></td><td>Current effective caster level.</td></tr>
<tr><td><code>casting.class_levels</code></td><td>Levels currently contributing to the casting profile.</td></tr>
<tr><td><code>spell_points.current</code>, <code>.maximum</code>, <code>.temporary</code></td><td>Built-in spell-point values.</td></tr>
<tr><td><code>hit_points.current</code>, <code>.maximum</code>, <code>.temporary</code>, <code>.nonlethal</code></td><td>Built-in hit-point values.</td></tr>
<tr><td><code>favored_class.hp</code>, <code>.skill_points</code>, <code>.manual</code></td><td>Totals allocated through the Page 0 favored-class bonus block.</td></tr>
<tr><td><code>movement.land_speed</code>, <code>.armor_speed</code>, <code>.fly_speed</code>, <code>.swim_speed</code>, <code>.climb_speed</code>, <code>.burrow_speed</code>, <code>.teleport_speed</code></td><td>Current effective movement values in feet, including automatic effects.</td></tr>
<tr><td><code>skills.acrobatics</code> or <code>skills.acrobatics.total</code></td><td>The current calculated skill total. Skill names use lowercase underscores.</td></tr>
<tr><td><code>skills.acrobatics.ranks</code> or <code>skillranks.acrobatics</code></td><td>Ranks invested in the named skill.</td></tr>
<tr><td><code>feats.power_attack</code> or <code>feat.power_attack</code></td><td>1 when the named feat is owned and enabled; otherwise 0.</td></tr>
<tr><td><code>feats.power_attack.owned</code></td><td>1 when the character owns the feat, even if it is currently disabled.</td></tr>
<tr><td><code>feats.power_attack.enabled</code></td><td>1 only while the feat is enabled.</td></tr>
<tr><td><code>martial_focus</code>, <code>martial_focus.active</code>, or <code>martial_focus.focused</code></td><td>1 while the character currently has martial focus; otherwise 0.</td></tr>
<tr><td><code>martial_focus.current</code>, <code>.maximum</code></td><td>Built-in martial-focus numeric values.</td></tr>
<tr><td><code>class_feature.inquisitor.judgment.current</code>, <code>.maximum</code>, <code>.active</code></td><td>The remaining uses, calculated maximum, and active state of the Inquisitor's Judgment. Other registered class resources use the same <code>class_feature.&lt;module&gt;.&lt;resource&gt;.&lt;value&gt;</code> pattern.</td></tr>
<tr><td><code>class_feature.inquisitor.bane.current</code>, <code>.maximum</code>, <code>.active</code></td><td>The Inquisitor's remaining Bane rounds, calculated maximum, and active state.</td></tr>
<tr><td><code>class_feature.monk.ki_pool.current</code>, <code>.maximum</code></td><td>The chained Monk's current and calculated Ki Pool. Unchained Monk uses <code>class_feature.monk_unchained.ki_pool</code>.</td></tr>
<tr><td><code>class_feature.barbarian.rage.current</code>, <code>.maximum</code>, <code>.active</code></td><td>The Barbarian's remaining rage rounds and live rage state. Unchained Barbarian uses <code>class_feature.barbarian_unchained.rage</code>.</td></tr>
<tr><td><code>class_feature.bard.bardic_performance.current</code>, <code>.maximum</code>, <code>.active</code></td><td>The Bard's remaining performance rounds and whether the selected retained performance is active.</td></tr>
<tr><td><code>class_choice.wizard.arcane_school.selected</code>, <code>.count</code></td><td>Whether the class-choice slot is filled and how many options are selected.</td></tr>
<tr><td><code>class_choice.wizard.arcane_school.abjuration_school</code></td><td>1 when that specific school, domain, bloodline, mystery, bond, or other registered class option is selected; otherwise 0. Names use lowercase underscores.</td></tr>
<tr><td><code>class_power.oracle.oracle_revelations.count</code>, <code>.maximum</code></td><td>The selected and available revelation counts. Other systems use <code>class_power.&lt;class&gt;.&lt;system&gt;</code>.</td></tr>
<tr><td><code>class_power.barbarian.barbarian_rage_powers.superstition</code></td><td>1 when the named power is selected; otherwise 0. Rogue and slayer talents, discoveries, investigator talents, hexes, magus arcana, arcanist exploits, ninja tricks, ki powers, and revelations use the same pattern.</td></tr>
<tr><td><code>class_power.witch.witch_hexes.evil_eye.selected</code>, <code>.active</code></td><td>Separates ownership from the optional live toggle shown for situational powers. Full Rest ends active power toggles.</td></tr>
<tr><td><code>prodigy.level</code></td><td>Total levels in Prodigy.</td></tr>
<tr><td><code>prodigy.sequence.active</code>, <code>.links</code>, <code>.maximum</code>, <code>.remaining</code></td><td>The live Sequence state. The shorter aliases <code>sequence.active</code>, <code>sequence.links</code>, <code>sequence.maximum</code>, and <code>sequence.remaining</code> are equivalent.</td></tr>
<tr><td><code>prodigy.sequence.inspired_bonus</code>, <code>.effective_caster_level</code></td><td>The current Inspired Sequence bonus and Prodigy's resulting effective caster level.</td></tr>
<tr><td><code>prodigy.imbue.active</code>, <code>.selected</code>, <code>.value</code></td><td>Whether a valid imbue is active or selected, and its primary numeric benefit while active.</td></tr>
<tr><td><code>prodigy.imbue.life_regenerate.active</code>, <code>.selected</code>, <code>.value</code></td><td>Tests a specific imbue. For Regenerate, <code>.value</code> is its current Fast Healing.</td></tr>
<tr><td><code>prodigy.imbue.fast_healing</code>, <code>.teleport_distance</code>, <code>.burrow_speed</code>, <code>.radius</code></td><td>Named numeric imbue metrics. They are 0 while the corresponding imbue is inactive.</td></tr>
<tr><td><code>sphere.brute</code> or <code>sphere.warp</code></td><td>1 when the named martial or magical base sphere is possessed and enabled.</td></tr>
<tr><td><code>talent.brutal_strike</code></td><td>1 when the named martial or magical talent is owned and enabled. <code>.owned</code> and <code>.enabled</code> are also available.</td></tr>
<tr><td><code>talent.brute.brutal_strike</code></td><td>Sphere-scoped talent test. <code>martial_talent.brute.brutal_strike</code> and <code>magic_talent.warp.create_gap</code> are explicit system-scoped forms.</td></tr>
<tr><td><code>drawback.warp.limited_warp</code></td><td>1 when the named drawback is possessed for that sphere.</td></tr>
<tr><td><code>item.amulet_of_mighty_fists</code></td><td>1 when at least one copy is active (carried, worn, wielded, armor, or shield rather than stored).</td></tr>
<tr><td><code>item.amulet_of_mighty_fists.owned</code></td><td>1 when at least one copy is owned, even if stored.</td></tr>
<tr><td><code>item.amulet_of_mighty_fists.equipped</code>, <code>.worn</code>, <code>.wielded</code>, or <code>.carried</code></td><td>Tests the current state of at least one copy.</td></tr>
<tr><td><code>item.amulet_of_mighty_fists.quantity</code></td><td>Total quantity of every inventory row with this name.</td></tr>
</table>

<h2>Custom tracker references</h2>
<p>Every custom block has a stable reference key. If the key is <code>ki_pool</code>, formulas may use:</p>
<ul>
<li><code>trackers.ki_pool.value</code> — the calculated value, or the counter/pool’s current value.</li>
<li><code>trackers.ki_pool.maximum</code> — its formula-derived or manual maximum.</li>
<li><code>trackers.ki_pool.current</code> — its manually tracked current value.</li>
<li><code>trackers.ki_pool.temporary</code> — its temporary value.</li>
</ul>
<p>Moving, resizing, recoloring, or renaming the visible block does not break a formula. Changing its reference key does require dependent formulas to be updated. Circular references are detected and displayed as errors.</p>

<h2>Operators</h2>
<p><code>+</code> add, <code>-</code> subtract, <code>*</code> multiply, <code>/</code> divide, <code>//</code> floor division, <code>%</code> remainder, and <code>**</code> exponentiation. Parentheses control order.</p>
<p>Comparisons use <code>==</code>, <code>!=</code>, <code>&lt;</code>, <code>&lt;=</code>, <code>&gt;</code>, and <code>&gt;=</code>. Conditions may use <code>and</code> or its interchangeable short form <code>&amp;</code>, plus <code>or</code>, <code>not</code>, and the form <code>value_if_true if condition else value_if_false</code>.</p>

<h2>Functions</h2>
<table cellspacing="7">
<tr><th>Function</th><th>Purpose</th><th>Example</th></tr>
<tr><td><code>floor(value)</code></td><td>Rounds downward.</td><td><code>floor(8 / 3)</code> gives 2.</td></tr>
<tr><td><code>ceil(value)</code></td><td>Rounds upward.</td><td><code>ceil(8 / 3)</code> gives 3.</td></tr>
<tr><td><code>round(value)</code></td><td>Rounds to the nearest whole number.</td><td><code>round(2.6)</code> gives 3.</td></tr>
<tr><td><code>min(a, b, ...)</code></td><td>Returns the smallest supplied value.</td><td><code>min(character.level, 10)</code> caps a value at 10.</td></tr>
<tr><td><code>max(a, b, ...)</code></td><td>Returns the largest supplied value.</td><td><code>max(1, abilities.wisdom.modifier)</code> sets a minimum of 1.</td></tr>
<tr><td><code>clamp(value, minimum, maximum)</code></td><td>Keeps a value inside a range.</td><td><code>clamp(character.level, 1, 5)</code>.</td></tr>
<tr><td><code>abs(value)</code></td><td>Returns the distance from zero.</td><td><code>abs(-3)</code> gives 3.</td></tr>
<tr><td><code>IF(condition, true_value, false_value)</code></td><td>Returns only the matching branch. The unused branch is not evaluated.</td><td><code>IF(martial_focus, 2, 0)</code>.</td></tr>
<tr><td><code>dice(count, sides)</code> or <code>XdY</code></td><td>Represents a genuine dice roll. Attack-damage fields preserve the notation until the attack is rolled; calculated result fields roll when evaluated. Counts are limited to 1,000 dice.</td><td><code>dice(3, 8)</code> and <code>3d8</code> are equivalent.</td></tr>
</table>
<p>Dice are genuine rolls, never averages. In an attack's Additional Damage formula, <code>=1d6+1d4</code> remains visible as dice and both terms are rolled only when the attack is rolled. Other live calculated fields can evaluate again when dependencies refresh, so avoid dice in permanent statistics such as maximum HP.</p>
<p>Function arguments may use commas or European spreadsheet-style semicolons: <code>IF(martial_focus; 2; 0)</code> is the same as <code>IF(martial_focus, 2, 0)</code>.</p>

<h2>Pool recipes</h2>
<h3>One point every three Monk levels</h3>
<p><code>floor(classes.monk.level / 3)</code></p>
<h3>Ki-style pool</h3>
<p><code>floor(classes.monk.level / 2) + abilities.wisdom.modifier</code></p>
<h3>Level plus casting ability, minimum 1</h3>
<p><code>max(1, character.level + abilities.charisma.modifier)</code></p>
<h3>Half level, rounded up</h3>
<p><code>ceil(character.level / 2)</code></p>
<h3>Dependent reserve pool</h3>
<p><code>trackers.primary_pool.maximum + abilities.wisdom.modifier</code></p>
<h3>Piranha Strike-style BAB penalty</h3>
<p><code>-floor((bab + 3) / 4) if feats.piranha_strike else 0</code></p>
<h3>Focus-gated bonus</h3>
<p><code>2 if martial_focus else 0</code></p>
<h3>Sphere, drawback, and item condition</h3>
<p><code>IF(martial_focus &amp; sphere.brute &amp; item.belt_of_giant_strength.equipped, bab * 2, 0)</code></p>
<h3>Talent-gated damage roll</h3>
<p><code>IF(martial_focus &amp; talent.brutal_strike, 3d8 * floor(character.level / 5), 0)</code></p>
<h3>Movement based on another statistic</h3>
<p><code>abilities.dexterity.score * 5</code> — for example, Dexterity 12 resolves to 60 feet. Every movement base/override field accepts the same formula language.</p>
<h3>Movement granted by an active Prodigy imbue</h3>
<p><code>IF(prodigy.imbue.warp_step_between.active, prodigy.imbue.teleport_distance, 0)</code> — displays Step Between's current teleport distance only while the Warp imbue is active. Movement formulas update immediately when links or the active imbue change.</p>
<h3>Sequence-scaled value</h3>
<p><code>IF(sequence.active, sequence.links * 5, 0)</code> — grants 5 points per current link while a sequence is active.</p>
<h3>Class-feature state</h3>
<p><code>IF(class_feature.inquisitor.judgment.active, 2, 0)</code> — returns 2 only while the Inquisitor's Judgment is active. Resource references update immediately when uses, choices, activation, class level, or archetype change.</p>
<h3>Class choice</h3>
<p><code>IF(class_choice.wizard.arcane_school.abjuration_school, 2, 0)</code> — returns 2 only when Abjuration is the selected Arcane School. The same pattern works for domains, inquisitions, bloodlines, mysteries, opposition schools, and bonds.</p>
<h3>Class power</h3>
<p><code>IF(class_power.barbarian.barbarian_rage_powers.superstition, 2, 0)</code> — returns 2 only when Superstition is among the selected rage powers. The same pattern works for every registered recurring class power.</p>
<p><code>IF(class_power.witch.witch_hexes.iceplant, 2, 0)</code> — returns 2 when the Witch has selected Iceplant. Use autocomplete to discover the normalized class, system, and power names.</p>

<h2>Safety and errors</h2>
<p>Only the documented arithmetic, references, comparisons, and functions are accepted. Formulas cannot open files, run programs, access the network, call arbitrary Python, or execute SQL. Unknown names, division by zero, excessive values, and dependency cycles appear as readable formula errors without damaging the character file.</p>
"""

FORMULA_SEARCH_TEXT = """
Formula language calculated value counter resource pool named reference character level total level BAB
autocomplete autofill suggestion dropdown current value keyboard arrows enter tab escape
formula fields attack damage movement maximum HP martial focus casting class caster level spell point skill misc sphere DC equipment weight value armor enhancement custom modifier feat trait
class level ability score modifier caster level casting class levels spell points hit points martial focus focused
class feature resource inquisitor judgment bane discern lies teamwork swaps monk ki pool barbarian rage current maximum active archetype class choice domain inquisition bloodline mystery school bond selected count class power ki power rage power revelation rogue talent slayer talent alchemist discovery investigator talent witch hex magus arcana arcanist exploit ninja trick
prodigy level sequence active links maximum remaining inspired bonus effective caster level imbue selected active value fast healing teleport distance
favored class bonus hp skill points manual movement land armor fly swim climb burrow teleport speed
skills skill total skill ranks skillranks feats feat owned enabled power attack piranha strike BAB
sphere base sphere talent talents martial talent magic talent brutal strike drawback martial magical item inventory owned active equipped worn wielded carried quantity
custom tracker value maximum current temporary operators add subtract multiply divide floor division remainder
exponent comparisons boolean condition if else IF function functions floor ceil round min max clamp abs dice roll d6 d8 d20 examples recipes
full rest safe formulas circular dependency unknown reference division by zero
"""
