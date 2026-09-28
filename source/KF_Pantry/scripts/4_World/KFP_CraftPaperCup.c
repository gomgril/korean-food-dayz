// Vanilla Paper is a non-quantity item: two distinct objects are two sheets.
class KFP_CraftPaperCup: RecipeBase
{
    override void Init()
    {
        m_Name = KF_Lang.Text("STR_KF_R_PAPERCUP");
        m_IsInstaRecipe = false;
        m_AnimationLength = 3 / CRAFTING_TIME_UNIT_SIZE;
        m_Specialty = 0;
        m_AnywhereInInventory = false;

        for (int i = 0; i < 2; i++)
        {
            InsertIngredient(i, "Paper");
            m_MinDamageIngredient[i] = -1;
            m_MaxDamageIngredient[i] = 3;
            m_MinQuantityIngredient[i] = -1;
            m_MaxQuantityIngredient[i] = -1;
            m_IngredientAddHealth[i] = 0;
            m_IngredientSetHealth[i] = -1;
            m_IngredientAddQuantity[i] = 0;
            m_IngredientDestroy[i] = true;
            m_IngredientUseSoftSkills[i] = false;
        }

        AddResult("KF_PaperCup");
        m_ResultSetFullQuantity[0] = false;
        m_ResultSetQuantity[0] = -1;
        m_ResultSetHealth[0] = -1;
        m_ResultInheritsHealth[0] = -2;
        m_ResultInheritsColor[0] = -1;
        m_ResultToInventory[0] = -1; // Native inventory-first, ground fallback.
        m_ResultUseSoftSkills[0] = false;
        m_ResultReplacesIngredient[0] = -1;
    }

    override bool CanDo(ItemBase ingredients[], PlayerBase player)
    {
        // Do not server-gate this method: clients need it to display the recipe.
        if (!player || !ingredients[0] || !ingredients[1]) return false;
        if (ingredients[0] == ingredients[1]) return false;
        for (int i = 0; i < 2; i++)
        {
            ItemBase paper = ingredients[i];
            // InsertIngredient accepts subclasses; do not consume keycards/leaflets.
            if (paper.GetType() != "Paper" || paper.HasQuantity()) return false;
            if (paper.IsSetForDeletion() || !KFP_Operations.Owned(paper, player)) return false;
            if (vector.Distance(paper.GetPosition(), player.GetPosition()) >= ACCEPTABLE_DISTANCE) return false;
        }
        return super.CanDo(ingredients, player);
    }

    override void PerformRecipe(ItemBase item1, ItemBase item2, PlayerBase player)
    {
        // Native PerformRecipe consumes ingredients even if result creation fails.
        // Create successfully before applying any ingredient modifications.
        if (!GetGame().IsServer() || !player || !item1 || !item2) return;
        if (!CheckRecipe(item1, item2, player)) return;
        ItemBase cup = CreateCup(player);
        if (!cup) return;
        array<ItemBase> results = new array<ItemBase>;
        results.Insert(cup);
        ApplyModificationsResults(m_IngredientsSorted, results, null, player);
        ApplyModificationsIngredients(m_IngredientsSorted, player);
        Do(m_IngredientsSorted, player, results, m_Specialty);
        DeleleIngredientsPass();
    }

    protected ItemBase CreateCup(PlayerBase player)
    {
        ItemBase cup = ItemBase.Cast(player.GetInventory().CreateInInventory("KF_PaperCup"));
        if (!cup) cup = ItemBase.Cast(KF_Cooking.SpawnResult(player, "KF_PaperCup"));
        return cup;
    }
};
